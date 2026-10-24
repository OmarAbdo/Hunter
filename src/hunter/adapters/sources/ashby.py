"""One company's Ashby board (docs/sources.md): every listed job, placed by its address and
workplace type, with the employer's own job id, so Hunter can apply on Ashby itself."""

from typing import Any

from hunter.adapters.sources.reading import parsed_time, place_at, read_json
from hunter.adapters.web_client import WebClient
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import EmployerRef, Employment, Posting, SourceRef

API = "https://api.ashbyhq.com"
WORKPLACES = {"OnSite": Workplace.ONSITE, "Hybrid": Workplace.HYBRID, "Remote": Workplace.REMOTE}
EMPLOYMENT = {
    "FullTime": Employment.FULL_TIME,
    "PartTime": Employment.PART_TIME,
    "Intern": Employment.INTERNSHIP,
    "Contract": Employment.CONTRACT,
    "Temporary": Employment.TEMPORARY,
}


class AshbyFeed:
    def __init__(self, web: WebClient, board: str, company: str, api: str = API) -> None:
        self.web = web
        self.board = board
        self.company = company
        self.api = api

    @property
    def name(self) -> str:
        return f"ashby:{self.board}"

    def fetch(self) -> list[Posting]:
        url = f"{self.api}/posting-api/job-board/{self.board}"
        answer = read_json(self.web, url, {"includeCompensation": "true"})
        return [self._posting(job) for job in answer["jobs"] if job.get("isListed", True)]

    def _posting(self, job: dict[str, Any]) -> Posting:
        workplace = workplace_of(job)
        return Posting(
            title=job["title"].strip(),
            company=self.company,
            location=place_of(job, workplace),
            other_locations=tuple(
                place_of(entry, workplace) for entry in job.get("secondaryLocations") or []
            ),
            source=SourceRef(source="ashby", native_id=job["id"]),
            employer=EmployerRef(ats="ashby", board=self.board, job_id=job["id"]),
            employment=EMPLOYMENT.get(job.get("employmentType") or ""),
            url=job["jobUrl"],
            apply_url=job["applyUrl"],
            description=job.get("descriptionPlain") or "",
            posted_at=parsed_time(job.get("publishedAt")),
        )


def workplace_of(job: dict[str, Any]) -> Workplace | None:
    named = WORKPLACES.get(job.get("workplaceType") or "")
    return named or (Workplace.REMOTE if job.get("isRemote") else None)


def place_of(entry: dict[str, Any], workplace: Workplace | None) -> Location:
    """A job's or a secondary location's place, from its postal address when it has one. A remote
    job is open to the country of its address."""
    address = (entry.get("address") or {}).get("postalAddress") or {}
    parts = (address.get("addressLocality"), address.get("addressCountry"))
    text = ", ".join(part for part in parts if part) or entry.get("location", "")
    return place_at(text, workplace)
