"""One company's Workday career site (docs/sources.md), searched with a JSON body. The board is
`tenant/wdN/site`, as in `nvidia/wd5/NVIDIAExternalCareerSite`. Large companies list thousands of
jobs, newest first; a run reads the newest 200. The list holds no descriptions."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from hunter.adapters.sources.reading import place_at, read_posted_json
from hunter.adapters.web_client import WebClient
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

API = "https://{tenant}.{instance}.myworkdayjobs.com"
PAGE = 20
MOST_PAGES = 10
AGE = re.compile(
    r"posted (?:(?P<today>today)|(?P<yesterday>yesterday)|(?P<days>\d+)\+? days? ago)", re.I
)
SEVERAL_PLACES = re.compile(r"^\d+ locations?$", re.I)
COUNTRY_CODE = re.compile(r"[A-Z]{2}")


class WorkdayFeed:
    def __init__(self, web: WebClient, board: str, company: str, api: str = API) -> None:
        self.web = web
        self.board = board
        self.company = company
        tenant, instance, site = board.split("/")
        host = {"tenant": tenant, "instance": instance}
        self.search = api.format(**host) + f"/wday/cxs/{tenant}/{site}/jobs"
        self.pages = API.format(**host) + f"/{site}"  # where the jobs are shown

    @property
    def name(self) -> str:
        return f"workday:{self.board}"

    def fetch(self) -> list[Posting]:
        now = datetime.now(UTC)
        postings: list[Posting] = []
        total = 0
        for page in range(MOST_PAGES):
            body = {"appliedFacets": {}, "limit": PAGE, "offset": page * PAGE, "searchText": ""}
            answer = read_posted_json(self.web, self.search, body)
            postings += [self._posting(job, now) for job in answer["jobPostings"]]
            total = answer.get("total") or total  # Workday gives the total on the first page only
            if (page + 1) * PAGE >= total:
                break
        return postings

    def _posting(self, job: dict[str, Any], now: datetime) -> Posting:
        job_id = (job.get("bulletFields") or [""])[0]
        path = job.get("externalPath") or ""
        return Posting(
            title=job["title"].strip(),
            company=self.company,
            location=place_of(job.get("locationsText") or "", path),
            source=SourceRef(source="workday", native_id=job_id),
            employer=EmployerRef(ats="workday", board=self.board, job_id=job_id),
            url=f"{self.pages}{path}",
            apply_url=f"{self.pages}{path}",
            posted_at=posted_at(job.get("postedOn") or "", now),
        )


def place_of(text: str, path: str) -> Location:
    """From "US, CA, Santa Clara", or for "2 Locations" from the first one's job link
    (/job/US-CA-Santa-Clara/…)."""
    if SEVERAL_PLACES.match(text):
        words = path.split("/")[2].split("-") if path.count("/") > 1 else []
    else:
        words = [word.strip() for word in text.split(",")]
    return place_from_words(words)


def place_from_words(words: list[str]) -> Location:
    """Workday writes a country code first, then for the US a state code, then the city. The
    state is skipped, so CA reads as California's state and not as Canada."""
    if words and COUNTRY_CODE.fullmatch(words[0]):
        city = " ".join(word for word in words[1:] if not COUNTRY_CODE.fullmatch(word))
        return place_at(f"{city}, {words[0]}", None)
    return place_at(", ".join(words), None)


def posted_at(text: str, now: datetime) -> datetime | None:
    """The date in "Posted Today", "Posted Yesterday", "Posted 3 Days Ago" or
    "Posted 30+ Days Ago"."""
    age = AGE.search(text)
    if age is None:
        return None
    days = 0 if age["today"] else 1 if age["yesterday"] else int(age["days"])
    return now - timedelta(days=days)
