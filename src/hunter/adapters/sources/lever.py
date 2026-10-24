"""One company's Lever board (docs/sources.md). Lever hosts companies in the EU on a separate API,
so a board that isn't on the first host is looked for on the second."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from hunter.adapters.html_text import plain_text
from hunter.adapters.sources.reading import employment_from, place_at, read_json
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Workplace
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

HOSTS = ("https://api.lever.co", "https://api.eu.lever.co")
WORKPLACES = {"onsite": Workplace.ONSITE, "hybrid": Workplace.HYBRID, "remote": Workplace.REMOTE}


class LeverFeed:
    def __init__(
        self, web: WebClient, board: str, company: str, api: str | Sequence[str] = HOSTS
    ) -> None:
        self.web = web
        self.board = board
        self.company = company
        self.hosts = (api,) if isinstance(api, str) else tuple(api)

    @property
    def name(self) -> str:
        return f"lever:{self.board}"

    def fetch(self) -> list[Posting]:
        for host in self.hosts[:-1]:
            found = self._read_unless_gone(host)
            if found is not None:
                return found
        return self._read(self.hosts[-1])

    def _read_unless_gone(self, host: str) -> list[Posting] | None:
        try:
            return self._read(host)
        except SourceUnavailableError as error:
            if error.gone:
                return None
            raise

    def _read(self, host: str) -> list[Posting]:
        answer = read_json(self.web, f"{host}/v0/postings/{self.board}", {"mode": "json"})
        return [self._posting(job) for job in answer]

    def _posting(self, job: dict[str, Any]) -> Posting:
        categories = job.get("categories") or {}
        workplace = WORKPLACES.get(job.get("workplaceType") or "")
        cities = categories.get("allLocations") or [categories.get("location") or ""]
        place, *other_places = [
            place_at(f"{city}, {job.get('country') or ''}", workplace) for city in cities
        ]
        return Posting(
            title=job["text"].strip(),
            company=self.company,
            location=place,
            other_locations=tuple(other_places),
            source=SourceRef(source="lever", native_id=job["id"]),
            employer=EmployerRef(ats="lever", board=self.board, job_id=job["id"]),
            employment=employment_from(categories.get("commitment")),
            url=job["hostedUrl"],
            apply_url=job["applyUrl"],
            description=description_of(job),
            posted_at=datetime.fromtimestamp(job["createdAt"] / 1000, UTC),
        )


def description_of(job: dict[str, Any]) -> str:
    """Lever splits a description into an intro, lists ("What you'll do") and a closing part."""
    lists = [
        f"{entry.get('text', '')}\n{plain_text(entry.get('content'))}"
        for entry in job.get("lists") or []
    ]
    parts = [job.get("descriptionPlain") or "", *lists, job.get("additionalPlain") or ""]
    return "\n\n".join(part.strip() for part in parts if part.strip())
