"""USAJobs' search API (docs/sources.md), the US government's jobs: a keyed search over federal
openings, in the US and at its posts abroad. A search looks for jobs published in the last 30
days, in the place when one is given, 100 a page, up to 3 pages. USAJobs wants the account's mail
as the User-Agent, in place of Hunter's own, with the key (`[keys.usajobs]` in var/accounts.toml).
Jobs link to their page on usajobs.gov, where they're applied to, and name every place they're
open in; the description is the job's summary. USAJobs marks remote jobs and those that allow
telework, which Hunter takes as hybrid. It publishes no rate limit, only 500 jobs a page and
10,000 a search."""

from datetime import UTC
from typing import Any

from hunter.adapters.sources.reading import parsed_time, place_at, read_json
from hunter.adapters.sources.searches.keyed import keeping_keys_out
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.campaign import Search
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import Employment, Posting, SourceRef

API = "https://data.usajobs.gov/api"
PAGE_SIZE = 100
MOST_PAGES = 3  # 300 jobs
DAYS = "30"
# USAJobs' position schedule codes (its code list `positionscheduletypes`); the others are shift
# work, intermittent, job sharing and multiple schedules.
SCHEDULES = {"1": Employment.FULL_TIME, "2": Employment.PART_TIME}


class UsaJobsSearch:
    def __init__(self, web: WebClient, search: Search, key: dict[str, Any], api: str = API) -> None:
        self.web = web
        self.search = search
        self.key = key
        self.api = api

    @property
    def name(self) -> str:
        place = f"@{self.search.place}" if self.search.place else ""
        return f"usajobs:{self.search.query}{place}"

    def fetch(self) -> list[Posting]:
        if self.search.country not in ("", "US"):
            raise SourceUnavailableError(f"{self.name}: USAJobs searches only the US")
        postings: list[Posting] = []
        for page in range(1, MOST_PAGES + 1):
            jobs = self._jobs(page)
            postings.extend(map(posting_of, jobs))
            if len(jobs) < PAGE_SIZE:
                break
        return postings

    def _jobs(self, page: int) -> list[dict[str, Any]]:
        params = {
            "Keyword": self.search.query,
            **({"LocationName": self.search.place} if self.search.place else {}),
            "DatePosted": DAYS,
            "ResultsPerPage": str(PAGE_SIZE),
            "Page": str(page),
        }
        url, headers = f"{self.api}/search", request_headers(self.key)
        answer = keeping_keys_out(
            lambda: read_json(self.web, url, params, headers), self.key.values()
        )
        result = answer.get("SearchResult") or {} if isinstance(answer, dict) else {}
        jobs: list[dict[str, Any]] = result.get("SearchResultItems") or []
        return jobs


def request_headers(key: dict[str, Any]) -> dict[str, str]:
    """USAJobs asks for the account's mail as the User-Agent."""
    return {"User-Agent": key["email"], "Authorization-Key": key["api_key"]}


def posting_of(item: dict[str, Any]) -> Posting:
    job = item.get("MatchedObjectDescriptor") or {}
    details = (job.get("UserArea") or {}).get("Details") or {}
    place, *other_places = places_of(job.get("PositionLocation") or [], workplace_of(details))
    schedule: dict[str, Any] = next(iter(job.get("PositionSchedule") or []), {})
    posted_at = parsed_time(job.get("PublicationStartDate"))
    return Posting(
        title=(job.get("PositionTitle") or "").strip(),
        company=(job.get("OrganizationName") or "").strip(),
        location=place,
        other_locations=tuple(other_places),
        source=SourceRef(source="usajobs", native_id=str(item["MatchedObjectId"])),
        employment=SCHEDULES.get(str(schedule.get("Code"))),
        url=link(job.get("PositionURI")),
        apply_url=link(next(iter(job.get("ApplyURI") or []), job.get("PositionURI"))),
        description=(details.get("JobSummary") or "").strip(),
        posted_at=posted_at.replace(tzinfo=UTC) if posted_at else None,  # no zone: taken as UTC
    )


def places_of(locations: list[dict[str, Any]], workplace: Workplace) -> list[Location]:
    """Every place the job names, each once. A place's city comes with its state ("Seattle,
    Washington"), and only the city is read: states share their names with towns elsewhere, so
    "Warren AFB, Wyoming" would be put in Wyoming, Michigan. A remote job's place is "Anywhere in
    the U.S. (remote job)"."""
    places = [
        place_at(f"{city_of(spot)}, {spot.get('CountryCode') or 'US'}", workplace)
        for spot in locations
    ]
    return list(dict.fromkeys(places)) or [place_at("US", workplace)]


def city_of(spot: dict[str, Any]) -> str:
    return str(spot.get("CityName") or "").split(",")[0]


def workplace_of(details: dict[str, Any]) -> Workplace:
    if details.get("RemoteIndicator"):
        return Workplace.REMOTE
    return Workplace.HYBRID if details.get("TeleworkEligible") else Workplace.ONSITE


def link(address: str | None) -> str | None:
    """USAJobs writes its links with the default port: `https://www.usajobs.gov:443/job/…`."""
    return address.replace(".gov:443/", ".gov/") if address else None
