"""One company's rexx portal (docs/sources.md): the job list at
`<board>-portal.rexx-recruitment.com/stellenangebote.html`, 100 jobs a page (`?start=100`). Every
company styles its list differently, but every job links to a page ending in `-j<id>.html`, often
on the company's own career domain, and every job page carries schema.org `JobPosting` data. So
the list gives the jobs, and each job's page its details: one request per job."""

import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

from hunter.adapters.html_text import plain_text
from hunter.adapters.sources.reading import employment_from, parsed_time, place_at, read_page
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

API = "https://{board}-portal.rexx-recruitment.com"
PAGE_SIZE = 100
MOST_PAGES = 5  # 500 jobs, each one more request
JOB_LINK = re.compile(r"""href=["']([^"']*-j(\d+)\.html)[^"']*["']""")
POSTING_DATA = re.compile(
    r"""<script[^>]*application/ld\+json[^>]*>(.*?)</script>""", re.DOTALL | re.IGNORECASE
)


class RexxFeed:
    def __init__(self, web: WebClient, board: str, company: str, api: str = API) -> None:
        self.web = web
        self.board = board
        self.company = company
        self.api = api.format(board=board)

    @property
    def name(self) -> str:
        return f"rexx:{self.board}"

    def fetch(self) -> list[Posting]:
        postings = []
        for job_id, link in self._job_links().items():
            try:
                postings.append(self._posting(job_id, link))
            except SourceUnavailableError:
                continue  # one job's page that can't be read doesn't stop the others
        return postings

    def _job_links(self) -> dict[str, str]:
        """Page after page, until one isn't full or brings no job not already listed."""
        links: dict[str, str] = {}
        for page in range(MOST_PAGES):
            url = f"{self.api}/stellenangebote.html?start={page * PAGE_SIZE}"
            found = {
                job_id: urljoin(url, href)
                for href, job_id in JOB_LINK.findall(read_page(self.web, url))
            }
            new = found.keys() - links.keys()
            links.update(found)
            if not new or len(found) < PAGE_SIZE:
                break
        return links

    def _posting(self, job_id: str, link: str) -> Posting:
        data = posting_data(read_page(self.web, link))
        return Posting(
            title=str(data.get("title", "")).strip(),
            company=(data.get("hiringOrganization") or {}).get("name") or self.company,
            location=place_of(data),
            source=SourceRef(source="rexx", native_id=job_id),
            employer=EmployerRef(ats="rexx", board=self.board, job_id=job_id),
            employment=employment_from(str(data.get("employmentType") or "")),
            url=link,
            apply_url=link,
            description=plain_text(data.get("description")),
            posted_at=posted_on(data.get("datePosted")),
        )


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


def place_of(data: dict[str, Any]) -> Location:
    where: Any = data.get("jobLocation") or {}
    first: Any = where[0] if isinstance(where, list) and where else where
    address: dict[str, Any] = first.get("address") or {} if isinstance(first, dict) else {}
    return place_at(
        f"{address.get('addressLocality') or ''}, {address.get('addressCountry') or ''}", None
    )


def posted_on(text: str | None) -> datetime | None:
    """A date ("2026-10-08") is taken as the start of that day in UTC."""
    moment = parsed_time(text)
    return moment.replace(tzinfo=UTC) if moment and moment.tzinfo is None else moment
