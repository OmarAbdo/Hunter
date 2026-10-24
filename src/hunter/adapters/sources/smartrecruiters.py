"""One company's SmartRecruiters board (docs/sources.md): its postings, 100 at a time. The board is
the company's case-sensitive identifier, like `Brainlab`. The list holds no descriptions; they
come with a posting's own page."""

from typing import Any

from hunter.adapters.sources.reading import employment_from, parsed_time, place_at, read_json
from hunter.adapters.web_client import WebClient
from hunter.domain.discovery.location import Workplace
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

API = "https://api.smartrecruiters.com"
PAGE = 100
MOST = 1000  # postings read from one board in one run


class SmartRecruitersFeed:
    def __init__(self, web: WebClient, board: str, company: str, api: str = API) -> None:
        self.web = web
        self.board = board
        self.company = company
        self.api = api

    @property
    def name(self) -> str:
        return f"smartrecruiters:{self.board}"

    def fetch(self) -> list[Posting]:
        url = f"{self.api}/v1/companies/{self.board}/postings"
        postings: list[Posting] = []
        offset = 0
        while True:
            page = read_json(self.web, url, {"limit": str(PAGE), "offset": str(offset)})
            postings += [self._posting(job) for job in page["content"]]
            offset += PAGE
            if offset >= min(page.get("totalFound", 0), MOST):
                return postings

    def _posting(self, job: dict[str, Any]) -> Posting:
        where = job.get("location") or {}
        workplace = Workplace.REMOTE if where.get("remote") else None
        workplace = Workplace.HYBRID if where.get("hybrid") and not workplace else workplace
        country = (where.get("country") or "").upper()
        job_id = str(job["id"])
        page = f"https://jobs.smartrecruiters.com/{self.board}/{job_id}"
        return Posting(
            title=job["name"].strip(),
            company=(job.get("company") or {}).get("name") or self.company,
            location=place_at(f"{where.get('city') or ''}, {country}", workplace),
            source=SourceRef(source="smartrecruiters", native_id=job_id),
            employer=EmployerRef(ats="smartrecruiters", board=self.board, job_id=job_id),
            employment=employment_from((job.get("typeOfEmployment") or {}).get("label")),
            url=page,
            apply_url=page,
            posted_at=parsed_time(job.get("releasedDate")),
        )
