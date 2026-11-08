"""What every source adapter needs to read a source: its answer as JSON, with a failure of any kind
turned into SourceUnavailableError; times, places and employment types as sources write them."""

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime
from typing import Any

from hunter.adapters.html_text import plain_text
from hunter.adapters.places import place_from_text
from hunter.adapters.web_client import WebClient, WebError
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import Employment, Posting

GONE_STATUSES = frozenset({404, 410})
# A browser's identity, for sites that turn bots away (docs/sources.md, the bot rule).
BROWSER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36 Edg/157.0.0.0",
}
# A page's schema.org data, which job pages fill with a `JobPosting`.
POSTING_DATA = re.compile(
    r"""<script[^>]*application/ld\+json[^>]*>(.*?)</script>""", re.DOTALL | re.IGNORECASE
)
# What job sites write on the page of a job they took down, as pages read through Edge show it
# (their status isn't known): XING, StepStone, Adzuna.
GONE_PAGE = re.compile(
    r"isn.t available|nicht mehr (?:verfügbar|aktuell)|page not found|seite nicht gefunden",
    re.IGNORECASE,
)
# Words in a source's employment type, checked in this order: "Intern (full-time)" is an internship.
EMPLOYMENT_WORDS = (
    ("intern", Employment.INTERNSHIP),
    ("trainee", Employment.INTERNSHIP),
    ("parttime", Employment.PART_TIME),
    ("fulltime", Employment.FULL_TIME),
    ("permanent", Employment.FULL_TIME),
    ("contract", Employment.CONTRACT),
    ("freelance", Employment.CONTRACT),
    ("temporary", Employment.TEMPORARY),
)


def read_json(
    web: WebClient,
    url: str,
    params: Mapping[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
) -> Any:
    try:
        return web.get_json(url, params, headers)
    except WebError as error:
        raise SourceUnavailableError(str(error), gone=error.status in GONE_STATUSES) from error
    except ValueError as error:
        raise SourceUnavailableError(f"{url}: not JSON ({error})") from error


def read_posted_json(web: WebClient, url: str, body: object) -> Any:
    """For sources searched with a JSON body (Workday)."""
    try:
        return web.post_json(url, body)
    except WebError as error:
        raise SourceUnavailableError(str(error), gone=error.status in GONE_STATUSES) from error
    except ValueError as error:
        raise SourceUnavailableError(f"{url}: not JSON ({error})") from error


def read_text(
    web: WebClient,
    url: str,
    params: Mapping[str, str] | None = None,
    headers: Mapping[str, str] | None = None,
) -> str:
    """For sources that answer in XML or RSS."""
    try:
        return web.get_text(url, params, headers)
    except WebError as error:
        raise SourceUnavailableError(str(error), gone=error.status in GONE_STATUSES) from error


def read_page(web: WebClient, url: str) -> str:
    """For sources that are web pages: read only where the site's robots.txt allows it."""
    try:
        return web.get_page(url)
    except WebError as error:
        raise SourceUnavailableError(str(error), gone=error.status in GONE_STATUSES) from error


def parsed_time(text: str | None) -> datetime | None:
    """An ISO 8601 time ("…Z", "…+02:00", "… UTC"), or None when there is none or it can't
    be read."""
    try:
        return datetime.fromisoformat(text.replace(" UTC", "+00:00")) if text else None
    except ValueError:
        return None


def place_at(text: str, workplace: Workplace | None) -> Location:
    """The place the text names, with the workplace the source gives. A remote job is open to the
    country of its place."""
    place = place_from_text(text)
    if workplace is Workplace.REMOTE and place.country:
        return replace(place, workplace=workplace, remote_scope=frozenset({place.country}))
    return replace(place, workplace=workplace, remote_scope=frozenset())


def employment_from(text: str | None) -> Employment | None:
    """The employment type in words like "Full-time", "fulltime_permanent" or "Part time"."""
    letters = re.sub(r"[^a-z]", "", (text or "").lower())
    return next((kind for word, kind in EMPLOYMENT_WORDS if word in letters), None)


def posting_data(page: str) -> dict[str, Any]:
    """The page's schema.org `JobPosting`, or nothing when it has none."""
    items = [item for block in POSTING_DATA.findall(page) for item in data_items(block)]
    return next((item for item in items if item.get("@type") == "JobPosting"), {})


def data_items(block: str) -> list[dict[str, Any]]:
    try:
        found = json.loads(block)
    except ValueError:
        return []
    return [
        item for item in (found if isinstance(found, list) else [found]) if isinstance(item, dict)
    ]


class JobPageAds:
    """A job's whole ad from its own page's schema.org `JobPosting`, where its source's list gives
    none or only a few lines: softgarden's pages read over plain HTTP, Adzuna's through Edge.
    `page` reads a page and raises SourceUnavailableError."""

    def __init__(self, page: Callable[[str], str]) -> None:
        self.page = page

    def read(self, posting: Posting) -> str:
        return ad_on_page(self.page(posting.url), posting.url) if posting.url else ""


def ad_on_page(page: str, url: str) -> str:
    """The page's job ad. A page without one that says the job was taken down makes it gone; a
    page without one that doesn't has no ad."""
    description = posting_data(page).get("description")
    if not description and GONE_PAGE.search(page):
        raise SourceUnavailableError(f"{url}: the job is no longer there", gone=True)
    return plain_text(description)
