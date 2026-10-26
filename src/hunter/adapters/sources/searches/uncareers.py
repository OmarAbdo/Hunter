"""UN Careers (docs/sources.md), the United Nations Secretariat's jobs: the public search behind
careers.un.org/jobopening, read 100 jobs at a time, up to 300. It lists only open jobs. A search
looks for its query as one phrase in the jobs' text, duty stations included; its place is a duty
station ("Geneva", "New York") or a country as the UN writes it ("Kenya", "United States of
America"), and without one it covers every duty station.

Jobs name only their duty stations, so each search first reads UN Careers' list of duty stations
with their countries, which also turns the place into the stations searched. A job's company is
the UN entity that posts it, its title carries the grade ("Legal Officer, P3"), and its page on
careers.un.org is where it's applied to. Internships and consultancies say so; other jobs are
staff posts, permanent or temporary, which the list doesn't tell apart. Consultancies and some
internships name a work location: one that starts home-based or remote makes the job remote,
one that only allows remote work ("In-person in Doha or remote") doesn't. UN Careers publishes no
rate limit."""

import re
from typing import Any

from hunter.adapters.html_text import plain_text
from hunter.adapters.sources.reading import parsed_time, place_at, read_json, read_posted_json
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.campaign import Search
from hunter.domain.discovery.identity import text_key
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import Employment, Posting, SourceRef

API = "https://careers.un.org/api/public/opening"
JOB_PAGE = "https://careers.un.org/jobSearchDescription/{id}"
PAGE_SIZE = 100  # what the site itself asks for at most
MOST_PAGES = 3  # 300 jobs, the newest first
CATEGORIES = {"INT": Employment.INTERNSHIP, "CON": Employment.CONTRACT}
NO_COUNTRY = ("ALL", "-")  # the catch-all "OTHER", which holds every station, and Gaza
WORK_LOCATION = re.compile(r"Work Location</div>\s*<div[^>]*>(.*?)</div>", re.S)
HOME_BASED = re.compile(r"\W*(home|remote|working remotely)", re.I)  # matched at the start


class UnCareersSearch:
    def __init__(self, web: WebClient, search: Search, api: str = API) -> None:
        self.web = web
        self.search = search
        self.api = api

    @property
    def name(self) -> str:
        place = f"@{self.search.place}" if self.search.place else ""
        return f"uncareers:{self.search.query}{place}"

    def fetch(self) -> list[Posting]:
        places = self._places()
        stations = self._stations(places)
        jobs: dict[str, dict[str, Any]] = {}
        for page in range(MOST_PAGES):
            rows = self._rows(page, stations)
            new = {str(row["jobId"]): row for row in rows if str(row["jobId"]) not in jobs}
            jobs |= new
            if len(rows) < PAGE_SIZE or not new:
                break
        countries = station_countries(places)
        return [posting_from(job, countries) for job in jobs.values()]

    def _places(self) -> list[dict[str, Any]]:
        answer = read_json(self.web, f"{self.api}/jo-filter/list/v2/en")
        data = answer.get("data") if isinstance(answer, dict) else None
        if not isinstance(data, dict):
            raise SourceUnavailableError(f"{self.name}: an answer that isn't a list of places")
        places: list[dict[str, Any]] = (data.get("jl") or {}).get("values") or []
        return places

    def _stations(self, places: list[dict[str, Any]]) -> list[str]:
        if not self.search.place:
            return []
        stations = stations_in(self.search.place, places)
        if not stations:
            raise SourceUnavailableError(f"{self.name}: no duty station in {self.search.place}")
        return stations

    def _rows(self, page: int, stations: list[str]) -> list[dict[str, Any]]:
        body = search_body(self.search.query, stations, page)
        answer = read_posted_json(self.web, f"{self.api}/jo/list/filteredV2/en", body)
        data = answer.get("data") if isinstance(answer, dict) else None
        if not isinstance(data, dict):
            raise SourceUnavailableError(f"{self.name}: an answer that isn't a job list")
        rows: list[dict[str, Any]] = data.get("list") or []
        return rows


def search_body(query: str, stations: list[str], page: int) -> dict[str, Any]:
    """The search as careers.un.org sends it: its pages count from 0."""
    keyword = {"keyword": query} if query else {}
    return {
        "filterConfig": {**keyword, **({"ds": stations} if stations else {})},
        "pagination": {
            "page": page,
            "itemPerPage": PAGE_SIZE,
            "sortBy": "startDate",
            "sortDirection": -1,
        },
    }


def stations_in(place: str, places: list[dict[str, Any]]) -> list[str]:
    """The duty stations the place names, itself or by its country."""
    key = text_key(place)
    return [
        spot["code"]
        for spot in places
        if key in (text_key(spot.get("name") or ""), text_key(spot.get("countryName") or ""))
    ]


def station_countries(places: list[dict[str, Any]]) -> dict[str, str]:
    """The country of each station code jobs name."""
    return {
        station["code"]: spot["countryName"]
        for spot in places
        if spot.get("countryName") and spot["countryName"] not in NO_COUNTRY
        for station in spot.get("inspiraDutyStations") or []
    }


def posting_from(job: dict[str, Any], countries: dict[str, str]) -> Posting:
    workplace = workplace_of(job.get("jobDescription"))
    place, *other_places = places_of(job.get("dutyStation") or [], countries, workplace)
    page = JOB_PAGE.format(id=job["jobId"])
    return Posting(
        title=(job.get("postingTitle") or job.get("jobTitle") or "").strip(),
        company=((job.get("dept") or {}).get("name") or "").strip(),
        location=place,
        other_locations=tuple(other_places),
        source=SourceRef(source="uncareers", native_id=str(job["jobId"])),
        employment=CATEGORIES.get(job.get("categoryCode") or ""),
        url=page,
        apply_url=page,
        description=plain_text(job.get("jobDescription")),
        posted_at=parsed_time(job.get("startDate")),
    )


def places_of(
    stations: list[dict[str, Any]], countries: dict[str, str], workplace: Workplace | None
) -> list[Location]:
    places = [
        place_at(f"{station.get('description') or ''}, {country_of(station, countries)}", workplace)
        for station in stations
    ]
    return list(dict.fromkeys(places)) or [place_at("", workplace)]


def country_of(station: dict[str, Any], countries: dict[str, str]) -> str:
    return countries.get(str(station.get("code")), "")


def workplace_of(description: str | None) -> Workplace | None:
    """A work location like "Home based", "Remote or in Geneva", "Geneva" or "Flexible"."""
    found = WORK_LOCATION.search(description or "")
    return Workplace.REMOTE if found and HOME_BASED.match(found.group(1)) else None
