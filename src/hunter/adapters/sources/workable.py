"""One company's Workable board (docs/sources.md). Workable lists a job once for every city it's
open in, all under one shortcode; Hunter makes that one posting with all of its places."""

from dataclasses import replace
from typing import Any

from hunter.adapters.html_text import plain_text
from hunter.adapters.sources.reading import employment_from, parsed_time, place_at, read_json
from hunter.adapters.web_client import WebClient
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

API = "https://apply.workable.com"


class WorkableFeed:
    def __init__(self, web: WebClient, board: str, company: str, api: str = API) -> None:
        self.web = web
        self.board = board
        self.company = company
        self.api = api

    @property
    def name(self) -> str:
        return f"workable:{self.board}"

    def fetch(self) -> list[Posting]:
        url = f"{self.api}/api/v1/widget/accounts/{self.board}"
        answer = read_json(self.web, url, {"details": "true"})
        listings: dict[str, list[dict[str, Any]]] = {}
        for row in answer["jobs"]:
            listings.setdefault(row["shortcode"], []).append(row)
        company = answer.get("name") or self.company
        return [self._posting(rows, company) for rows in listings.values()]

    def _posting(self, rows: list[dict[str, Any]], company: str) -> Posting:
        job = rows[0]
        place, *other_places = places_of(
            rows, Workplace.REMOTE if job.get("telecommuting") else None
        )
        return Posting(
            title=job["title"].strip(),
            company=company,
            location=place,
            other_locations=tuple(other_places),
            source=SourceRef(source="workable", native_id=job["shortcode"]),
            employer=EmployerRef(ats="workable", board=self.board, job_id=job["shortcode"]),
            employment=employment_from(job.get("employment_type")),
            url=job.get("url") or job.get("shortlink"),
            apply_url=job.get("application_url"),
            description=plain_text(job.get("description")),
            posted_at=parsed_time(job.get("published_on") or job.get("created_at")),
        )


def places_of(rows: list[dict[str, Any]], workplace: Workplace | None) -> list[Location]:
    """One place per city the job is listed in. A remote job is open to all of their countries."""
    places = [
        place_at(f"{row.get('city') or ''}, {row.get('country') or ''}", workplace) for row in rows
    ]
    if workplace is not Workplace.REMOTE:
        return places
    scope = frozenset(place.country for place in places if place.country)
    return [replace(place, remote_scope=scope) for place in places]
