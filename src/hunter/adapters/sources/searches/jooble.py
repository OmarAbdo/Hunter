"""Jooble's job search API (docs/sources.md), a keyed aggregator: `POST jooble.org/api/<key>` with
the query, the place and the page, 20 jobs a page. Jooble issues a key per country site; Omar's is
for jooble.org, which answers a search for "Berlin" with jobs placed only in "Germany". Jobs link
to Jooble's page for them; the description is a snippet."""

from datetime import UTC, datetime
from typing import Any

from hunter.adapters.html_text import plain_text
from hunter.adapters.places import place_from_text
from hunter.adapters.sources.reading import employment_from, parsed_time, read_posted_json
from hunter.adapters.sources.searches.keyed import keeping_keys_out, without_tracking
from hunter.adapters.web_client import WebClient
from hunter.domain.discovery.campaign import Search
from hunter.domain.discovery.posting import Posting, SourceRef

API = "https://jooble.org/api"
PAGE_SIZE = 20
MOST_PAGES = 5  # 100 jobs


class JoobleSearch:
    def __init__(self, web: WebClient, search: Search, key: dict[str, Any], api: str = API) -> None:
        self.web = web
        self.search = search
        self.key = key
        self.api = api

    @property
    def name(self) -> str:
        place = f"@{self.search.place}" if self.search.place else ""
        country = f",{self.search.country}" if self.search.country else ""
        return f"jooble:{self.search.query}{place}{country}"

    def fetch(self) -> list[Posting]:
        """Page after page, until one isn't full or brings no job not already read."""
        postings: dict[str, Posting] = {}
        for page in range(1, MOST_PAGES + 1):
            jobs = self._jobs(page)
            found = {posting.source.native_id: posting for posting in map(self._posting, jobs)}
            new = found.keys() - postings.keys()
            postings.update(found)
            if not new or len(jobs) < PAGE_SIZE:
                break
        return list(postings.values())

    def _jobs(self, page: int) -> list[dict[str, Any]]:
        url, body = f"{self.api}/{self.key['api_key']}", search_body(self.search, page)
        answer = keeping_keys_out(lambda: read_posted_json(self.web, url, body), self.key.values())
        jobs: list[dict[str, Any]] = answer.get("jobs") or [] if isinstance(answer, dict) else []
        return jobs

    def _posting(self, job: dict[str, Any]) -> Posting:
        link = without_tracking(job.get("link") or "")
        return Posting(
            title=(job.get("title") or "").strip(),
            company=(job.get("company") or "").strip(),
            location=place_from_text(job.get("location") or "", self.search.country or None),
            source=SourceRef(source="jooble", native_id=str(job["id"])),
            employment=employment_from(job.get("type")),
            url=link,
            apply_url=link,
            description=plain_text(job.get("snippet")).replace("\xa0", " ").strip(),
            posted_at=in_utc(parsed_time(job.get("updated"))),
        )


def search_body(search: Search, page: int) -> dict[str, str]:
    return {"keywords": search.query, "location": search.place, "page": str(page)}


def in_utc(moment: datetime | None) -> datetime | None:
    """Jooble's times name no zone; they're taken as UTC."""
    return moment.replace(tzinfo=UTC) if moment and moment.tzinfo is None else moment
