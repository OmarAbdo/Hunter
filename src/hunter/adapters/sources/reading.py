"""What every source adapter needs to read a source: its answer as JSON, with a failure of any kind
turned into SourceUnavailableError; times, places and employment types as sources write them."""

import re
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime
from typing import Any

from hunter.adapters.places import place_from_text
from hunter.adapters.web_client import WebClient, WebError
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import Employment

GONE_STATUSES = frozenset({404, 410})
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


def read_text(web: WebClient, url: str, params: Mapping[str, str] | None = None) -> str:
    """For sources that answer in XML or RSS."""
    try:
        return web.get_text(url, params)
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
