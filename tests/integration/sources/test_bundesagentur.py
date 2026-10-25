from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from urllib.parse import urlencode

import pytest

from hunter.adapters.sources.searches import bundesagentur
from hunter.adapters.sources.searches.bundesagentur import BundesagenturSearch
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.campaign import Search
from hunter.domain.discovery.location import Workplace
from hunter.domain.discovery.posting import Employment

Pages = Callable[[Mapping[str, str]], str]
BERLIN = Search(source="bundesagentur", query="Software Engineer", place="Berlin")
SAVED = "bundesagentur-software-engineer-berlin.json"
JOB_PAGE = "https://www.arbeitsagentur.de/jobsuche/jobdetail/"


def page_path(page: int, *, place: bool = True, size: int = 100) -> str:
    where = {"wo": "Berlin", "umkreis": "25"} if place else {}
    params = {"was": "Software Engineer", **where, "angebotsart": "1", "veroeffentlichtseit": "30"}
    return f"/pc/v6/jobs?{urlencode({**params, 'size': str(size), 'page': str(page)})}"


def test_a_search_brings_the_jobs_it_finds(web: WebClient, source_pages: Pages) -> None:
    api = source_pages({page_path(1): SAVED})
    first, second, third, fourth = BundesagenturSearch(web, BERLIN, api=api).fetch()
    assert (first.title, first.company) == (
        "Senior Solution Engineer (m/w/d)",
        "Beta Systems Software AG",
    )
    assert (first.location.country, first.location.city) == ("DE", "Berlin")
    assert first.source.native_id == "12951-8e11200b-5a3a-4079--S"
    assert first.url == f"{JOB_PAGE}12951-8e11200b-5a3a-4079--S"
    assert (first.apply_url or "").startswith("https://www.heyjobs.co/")
    assert first.posted_at == datetime(2026, 9, 1, tzinfo=UTC)
    assert third.apply_url == third.url  # no link elsewhere: applied to on the Bundesagentur


def test_home_office_decides_the_workplace(web: WebClient, source_pages: Pages) -> None:
    api = source_pages({page_path(1): SAVED})
    jobs = BundesagenturSearch(web, BERLIN, api=api).fetch()
    workplaces = [job.location.workplace for job in jobs]
    assert workplaces == [Workplace.REMOTE, Workplace.ONSITE, Workplace.HYBRID, Workplace.HYBRID]
    assert jobs[0].location.remote_scope == frozenset({"DE"})


def test_working_hours_decide_the_employment(web: WebClient, source_pages: Pages) -> None:
    api = source_pages({page_path(1): SAVED})
    jobs = BundesagenturSearch(web, BERLIN, api=api).fetch()
    assert [job.employment for job in jobs] == [Employment.FULL_TIME] * 3 + [None]


def test_a_full_page_means_there_may_be_another_up_to_the_most_pages(
    web: WebClient, source_pages: Pages, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bundesagentur, "PAGE_SIZE", 4)
    monkeypatch.setattr(bundesagentur, "MOST_PAGES", 2)
    api = source_pages({page_path(1, size=4): SAVED, page_path(2, size=4): SAVED})
    assert len(BundesagenturSearch(web, BERLIN, api=api).fetch()) == 8


def test_a_search_without_a_place_covers_germany(web: WebClient, source_pages: Pages) -> None:
    germany = Search(source="bundesagentur", query="Software Engineer")
    search = BundesagenturSearch(web, germany, api=source_pages({page_path(1, place=False): SAVED}))
    assert search.name == "bundesagentur:Software Engineer"
    assert len(search.fetch()) == 4


def test_a_search_is_named_by_its_query_and_place(web: WebClient) -> None:
    assert BundesagenturSearch(web, BERLIN).name == "bundesagentur:Software Engineer@Berlin"


def test_an_answer_that_is_no_job_list_is_reported(web: WebClient, source_pages: Pages) -> None:
    api = source_pages({page_path(1): "lever-unzer.json"})
    with pytest.raises(SourceUnavailableError, match="isn't a job list"):
        BundesagenturSearch(web, BERLIN, api=api).fetch()
