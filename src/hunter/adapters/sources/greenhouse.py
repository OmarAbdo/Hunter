"""One company's Greenhouse board (docs/sources.md): every open job with its places and description,
and the employer's own job id, so Hunter can apply on Greenhouse itself."""

from typing import Any

from hunter.adapters.text.html_text import plain_text
from hunter.adapters.text.places import places_from_text
from hunter.adapters.sources.reading import parsed_time, read_json
from hunter.adapters.web.client import WebClient
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

API = "https://boards-api.greenhouse.io"


class GreenhouseFeed:
    def __init__(self, web: WebClient, board: str, company: str, api: str = API) -> None:
        self.web = web
        self.board = board
        self.company = company
        self.api = api

    @property
    def name(self) -> str:
        return f"greenhouse:{self.board}"

    def fetch(self) -> list[Posting]:
        url = f"{self.api}/v1/boards/{self.board}/jobs"
        answer = read_json(self.web, url, {"content": "true"})
        return [self._posting(job) for job in answer["jobs"]]

    def _posting(self, job: dict[str, Any]) -> Posting:
        job_id = str(job["id"])
        place, *other_places = places_from_text(job["location"]["name"])
        return Posting(
            title=job["title"].strip(),
            company=job.get("company_name") or self.company,
            location=place,
            other_locations=tuple(other_places),
            source=SourceRef(source="greenhouse", native_id=job_id),
            employer=EmployerRef(ats="greenhouse", board=self.board, job_id=job_id),
            url=job["absolute_url"],
            apply_url=job["absolute_url"],
            description=plain_text(job.get("content")),
            posted_at=parsed_time(job.get("first_published")),
        )
