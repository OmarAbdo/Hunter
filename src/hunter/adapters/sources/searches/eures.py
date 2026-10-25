"""EURES, the European Commission's job portal (docs/sources.md): the public search behind
europa.eu/eures/portal/jv-se, read 50 jobs at a time. A search looks for its query in job titles,
among jobs published in the last month; its place is a EURES location code, a country ("nl") or a
NUTS region ("de3" is Berlin), and without one it covers every EURES country.

Jobs are placed by their NUTS regions, named from Eurostat's NUTS 2024 table (`nuts.json`,
© EuroGeographics for the administrative boundaries). Most German jobs are the Bundesagentur's
own: their EURES id holds its reference number, so they join the Bundesagentur's jobs in the pool.
EURES often names the employer's website, which the Bundesagentur doesn't."""

import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hunter.adapters.html_text import plain_text
from hunter.adapters.sources.reading import place_at, read_posted_json
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.campaign import Search
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import Employment, Posting, SourceRef

API = "https://europa.eu/eures/api/jv-searchengine/public"
JOB_PAGE = "https://europa.eu/eures/portal/jv-se/jv-details/{id}"
PAGE_SIZE = 50  # the most EURES gives at once
MOST_PAGES = 40  # 2,000 jobs, the best matches first
BUNDESAGENTUR = "1"  # the EURES connection point that is the Bundesagentur
COUNTRIES = {"EL": "GR", "UK": "GB"}  # NUTS codes that aren't ISO 3166 codes
REGIONS: dict[str, str] = json.loads((Path(__file__).parent / "nuts.json").read_text("utf-8"))
SCHEDULES = (("fulltime", Employment.FULL_TIME), ("parttime", Employment.PART_TIME))


class EuresSearch:
    def __init__(self, web: WebClient, search: Search, api: str = API) -> None:
        self.web = web
        self.search = search
        self.api = api

    @property
    def name(self) -> str:
        place = f"@{self.search.place}" if self.search.place else ""
        return f"eures:{self.search.query}{place}"

    def fetch(self) -> list[Posting]:
        postings: list[Posting] = []
        for page in range(1, MOST_PAGES + 1):
            jobs = self._jobs(page)
            postings.extend(posting_from(job) for job in jobs)
            if len(jobs) < PAGE_SIZE:
                break
        return postings

    def _jobs(self, page: int) -> list[dict[str, Any]]:
        answer = read_posted_json(
            self.web, f"{self.api}/jv-search/search", search_body(self.search, page)
        )
        if not isinstance(answer, dict):
            raise SourceUnavailableError(f"{self.name}: an answer that isn't a job list")
        jobs: list[dict[str, Any]] = answer.get("jvs") or []
        return jobs


def search_body(search: Search, page: int) -> dict[str, Any]:
    """The search as the EURES portal sends it; the filters Hunter doesn't use stay empty."""
    unused = ("occupationUris", "skillUris", "requiredExperienceCodes", "positionScheduleCodes")
    more_unused = ("sectorCodes", "educationAndQualificationLevelCodes", "positionOfferingCodes")
    return {
        "resultsPerPage": PAGE_SIZE,
        "page": page,
        "sortSearch": "BEST_MATCH",
        "keywords": [{"keyword": search.query, "specificSearchCode": "TITLE"}],
        "publicationPeriod": "LAST_MONTH",
        "locationCodes": [search.place] if search.place else [],
        **{name: [] for name in (*unused, *more_unused, "euresFlagCodes", "otherBenefitsCodes")},
        "requiredLanguages": [],
        "minNumberPost": None,
        "sessionId": "hunter",
    }


def posting_from(job: dict[str, Any]) -> Posting:
    employer = job.get("employer") or {}
    place, *other_places = locations_of(job.get("locationMap") or {})
    created = job.get("creationDate")
    return Posting(
        title=job.get("title", "").strip(),
        company=(employer.get("name") or "").strip(),
        company_website=employer.get("website") or None,
        location=place,
        other_locations=tuple(other_places),
        source=SourceRef(source="eures", native_id=job["id"]),
        same_as=bundesagentur_job(job["id"]),
        employment=employment_of(job.get("positionScheduleCodes") or []),
        url=JOB_PAGE.format(id=job["id"]),
        apply_url=JOB_PAGE.format(id=job["id"]),
        description=plain_text(job.get("description")),
        posted_at=datetime.fromtimestamp(created / 1000, UTC) if created else None,
    )


def locations_of(regions_by_country: dict[str, list[str]]) -> list[Location]:
    """A place for every region the job is in, or its country when it names none."""
    places = [
        region_place(COUNTRIES.get(country, country), regions)
        for country, all_regions in regions_by_country.items()
        for regions in (all_regions or [""])
    ]
    return places or [Location()]


def region_place(country: str, region: str) -> Location:
    name = REGIONS.get(region, "")
    return place_at(f"{name}, {country}", None) if name else Location(country=country)


def bundesagentur_job(job_id: str) -> tuple[SourceRef, ...]:
    """A EURES id is base64 of "<the job's reference> <connection point>"."""
    try:
        reference, _, point = base64.b64decode(job_id + "==").decode().rpartition(" ")
    except ValueError:  # not base64, or not text
        return ()
    if point != BUNDESAGENTUR or not reference:
        return ()
    return (SourceRef(source="bundesagentur", native_id=reference),)


def employment_of(schedules: list[str]) -> Employment | None:
    return next((kind for code, kind in SCHEDULES if code in schedules), None)
