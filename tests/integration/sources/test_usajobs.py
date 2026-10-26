from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from urllib.parse import urlencode

import pytest

from hunter.adapters.sources.searches import usajobs
from hunter.adapters.sources.searches.usajobs import UsaJobsSearch, places_of, request_headers
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.campaign import Search
from hunter.domain.discovery.location import Workplace
from hunter.domain.discovery.posting import Employment, Posting

Pages = Callable[[Mapping[str, str]], str]
WASHINGTON = Search(source="usajobs", query="software engineer", place="Washington, DC")
KEY = {"email": "someone@example.com", "api_key": "the-key"}
SAVED = "usajobs-software-engineer.json"


def page_path(page: int, size: int = 100) -> str:
    search = {"Keyword": "software engineer", "LocationName": "Washington, DC", "DatePosted": "30"}
    return f"/search?{urlencode({**search, 'ResultsPerPage': str(size), 'Page': str(page)})}"


def postings(source_pages: Pages, web: WebClient) -> list[Posting]:
    return UsaJobsSearch(web, WASHINGTON, KEY, api=source_pages({page_path(1): SAVED})).fetch()


def test_a_search_brings_the_jobs_it_finds(source_pages: Pages, web: WebClient) -> None:
    tech_force, commission, smithsonian = postings(source_pages, web)
    assert (tech_force.title, tech_force.company) == (
        "IT Software Engineer (Tech Force)",
        "Office of Personnel Management",
    )
    assert tech_force.source.native_id == "888508400"
    assert tech_force.url == "https://www.usajobs.gov/job/888508400"
    assert tech_force.apply_url == "https://www.usajobs.gov/job/888508400"
    assert tech_force.employment is Employment.FULL_TIME
    assert commission.posted_at == datetime(2026, 10, 13, 14, 16, 37, 403000, tzinfo=UTC)
    assert commission.description.startswith("The Commission is seeking a Software Engineering")
    assert smithsonian.company == "Smithsonian Institution"


def test_a_job_is_in_every_place_it_names_once(source_pages: Pages, web: WebClient) -> None:
    """The Tech Force job names 23 places, Washington and Kansas City twice."""
    tech_force, *_ = postings(source_pages, web)
    cities = [(place.country, place.city) for place in tech_force.locations]
    assert cities[:3] == [("US", "Washington"), ("US", "Salt Lake City"), ("US", "Seattle")]
    assert len(cities) == 21 and ("US", "Kansas City") in cities


def test_a_state_is_never_taken_for_a_town() -> None:
    """Wyoming and Washington are towns too (in Michigan, in the District of Columbia)."""
    bases = [
        {"CityName": "Warren AFB, Wyoming", "CountryCode": "United States"},
        {"CityName": "Fairchild AFB, Washington", "CountryCode": "United States"},
    ]
    assert [place.city for place in places_of(bases, Workplace.ONSITE)] == [None]


def test_a_job_is_remote_or_hybrid_as_usajobs_marks_it(source_pages: Pages, web: WebClient) -> None:
    tech_force, commission, smithsonian = postings(source_pages, web)
    assert tech_force.location.workplace is Workplace.ONSITE
    assert commission.location.workplace is Workplace.HYBRID  # telework eligible
    remote = smithsonian.location
    assert (remote.country, remote.city, remote.workplace) == ("US", None, Workplace.REMOTE)
    assert remote.remote_scope == frozenset({"US"})


def test_a_full_page_means_there_may_be_another_up_to_the_most_pages(
    source_pages: Pages, web: WebClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(usajobs, "PAGE_SIZE", 3)
    monkeypatch.setattr(usajobs, "MOST_PAGES", 2)
    api = source_pages({page_path(1, 3): SAVED, page_path(2, 3): SAVED})
    assert len(UsaJobsSearch(web, WASHINGTON, KEY, api=api).fetch()) == 6


def test_a_search_outside_the_us_is_refused(web: WebClient) -> None:
    berlin = Search(source="usajobs", query="software engineer", place="Berlin", country="DE")
    with pytest.raises(SourceUnavailableError, match="only the US"):
        UsaJobsSearch(web, berlin, KEY).fetch()


def test_a_search_is_named_by_its_query_and_place(web: WebClient) -> None:
    assert UsaJobsSearch(web, WASHINGTON, KEY).name == "usajobs:software engineer@Washington, DC"


def test_usajobs_is_asked_with_the_accounts_mail_and_key() -> None:
    """USAJobs wants the account's mail as the User-Agent, in place of Hunter's own."""
    assert request_headers(KEY) == {
        "User-Agent": "someone@example.com",
        "Authorization-Key": "the-key",
    }


def test_a_failed_search_never_shows_the_key(source_pages: Pages, web: WebClient) -> None:
    """Errors are printed in a run's report; the key and the mail are sent with every request."""
    with pytest.raises(SourceUnavailableError) as raised:
        UsaJobsSearch(web, WASHINGTON, KEY, api=source_pages({})).fetch()
    assert "the-key" not in str(raised.value) and "someone@example.com" not in str(raised.value)
