from collections.abc import Callable, Mapping
from datetime import UTC, datetime

import pytest

from hunter.adapters.sources.searches import uncareers
from hunter.adapters.sources.searches.uncareers import (
    UnCareersSearch,
    search_body,
    stations_in,
    workplace_of,
)
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.campaign import Search
from hunter.domain.discovery.location import Workplace
from hunter.domain.discovery.posting import Employment, Posting

Pages = Callable[[Mapping[str, str]], str]
GENEVA = Search(source="uncareers", query="geneva", place="Geneva")
LIST_PATH, PLACES_PATH = "/jo/list/filteredV2/en", "/jo-filter/list/v2/en"
SAVED = {LIST_PATH: "uncareers-geneva.json", PLACES_PATH: "uncareers-locations.json"}
PLACES = [
    {"name": "Geneva", "code": "Geneva", "countryName": "Switzerland"},
    {"name": "Nairobi", "code": "NAIROBI", "countryName": "Kenya"},
    {"name": "Gigiri", "code": "GIGIRI", "countryName": "Kenya"},
]


def fetched(web: WebClient, source_pages: Pages, search: Search = GENEVA) -> list[Posting]:
    return UnCareersSearch(web, search, api=source_pages(SAVED)).fetch()


def test_a_search_brings_the_jobs_it_finds(web: WebClient, source_pages: Pages) -> None:
    intern, *_ = fetched(web, source_pages)
    assert intern.title == "Intern for Risk Management and Peacebuilding Section"
    assert intern.company == "United Nations Environment Programme"
    assert (intern.location.country, intern.location.city) == ("CH", "Geneva")
    assert intern.source.native_id == "287097"
    assert intern.url == intern.apply_url == "https://careers.un.org/jobSearchDescription/287097"
    assert intern.posted_at == datetime(2026, 10, 26, 4, tzinfo=UTC)
    assert intern.description.startswith("Work Location")


def test_the_title_keeps_the_grade(web: WebClient, source_pages: Pages) -> None:
    *_, legal = fetched(web, source_pages)
    assert (legal.title, legal.company) == (
        "Legal Officer, P3",
        "Office of Administration of Justice",
    )


def test_every_duty_station_is_a_place_in_its_country(web: WebClient, source_pages: Pages) -> None:
    *_, legal = fetched(web, source_pages)
    places = [(place.country, place.city) for place in legal.locations]
    assert places == [("CL", "Santiago"), ("KE", "Nairobi"), ("TH", "Bangkok"), ("CH", "Geneva")]


def test_internships_and_consultancies_say_so(web: WebClient, source_pages: Pages) -> None:
    jobs = fetched(web, source_pages)
    assert [job.employment for job in jobs] == [Employment.INTERNSHIP, Employment.CONTRACT, None]


def test_a_home_based_job_is_remote(web: WebClient, source_pages: Pages) -> None:
    intern, consultant, _ = fetched(web, source_pages)
    assert intern.location.workplace is None
    assert consultant.location.workplace is Workplace.REMOTE


@pytest.mark.parametrize(
    ("work_location", "workplace"),
    [
        ("Working remotely / Home-based", Workplace.REMOTE),
        ("Remote or in Geneva, Switzerland", Workplace.REMOTE),
        ("In-Person in Doha, Qatar or remote", None),
        ("Internships can be conducted remotely or in-person", None),
    ],
)
def test_only_a_work_location_that_starts_remote_is_remote(
    work_location: str, workplace: Workplace | None
) -> None:
    item = f"<div>Work Location</div><div class='jobPostingItemContent'>{work_location}</div>"
    assert workplace_of(item) is workplace


def test_paging_stops_at_a_page_with_no_new_job(
    web: WebClient, source_pages: Pages, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(uncareers, "PAGE_SIZE", 3)
    assert len(fetched(web, source_pages)) == 3


def test_the_search_asks_for_the_query_in_the_duty_stations() -> None:
    body = search_body("political affairs", ["Geneva"], page=2)
    assert body["filterConfig"] == {"keyword": "political affairs", "ds": ["Geneva"]}
    assert body["pagination"] == {
        "page": 2,
        "itemPerPage": uncareers.PAGE_SIZE,
        "sortBy": "startDate",
        "sortDirection": -1,
    }
    assert search_body("", [], page=0)["filterConfig"] == {}


def test_a_place_is_a_duty_station_or_a_country() -> None:
    assert stations_in("geneva", PLACES) == ["Geneva"]
    assert stations_in("Kenya", PLACES) == ["NAIROBI", "GIGIRI"]
    assert stations_in("Berlin", PLACES) == []


def test_a_place_without_a_duty_station_is_reported(web: WebClient, source_pages: Pages) -> None:
    berlin = Search(source="uncareers", query="x", place="Berlin")
    with pytest.raises(SourceUnavailableError, match="no duty station in Berlin"):
        fetched(web, source_pages, berlin)


def test_a_search_without_a_place_covers_every_duty_station(
    web: WebClient, source_pages: Pages
) -> None:
    assert len(fetched(web, source_pages, Search(source="uncareers", query="geneva"))) == 3


def test_a_search_is_named_by_its_query_and_place(web: WebClient) -> None:
    assert UnCareersSearch(web, GENEVA).name == "uncareers:geneva@Geneva"
    assert UnCareersSearch(web, Search(source="uncareers", query="x")).name == "uncareers:x"


@pytest.mark.parametrize("path", [LIST_PATH, PLACES_PATH])
def test_an_answer_that_is_no_list_is_reported(
    web: WebClient, source_pages: Pages, path: str
) -> None:
    api = source_pages({**SAVED, path: "lever-unzer.json"})
    with pytest.raises(SourceUnavailableError, match="isn't a"):
        UnCareersSearch(web, GENEVA, api=api).fetch()
