from collections.abc import Callable
from datetime import date

import pytest

from hunter.adapters.sources.workable import WorkableFeed
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Workplace
from hunter.domain.discovery.posting import EmployerRef, Employment, Posting

JOBS = "/api/v1/widget/accounts/modash?details=true"
SourceApi = Callable[[str, str | None], str]


def postings(source_api: SourceApi, web: WebClient) -> list[Posting]:
    api = source_api(JOBS, "workable-modash.json")
    return WorkableFeed(web, "modash", "Modash", api=api).fetch()


def test_one_job_listed_in_six_cities_is_one_posting(
    source_api: SourceApi, web: WebClient
) -> None:
    backend, sales = postings(source_api, web)
    assert backend.title.startswith("Senior Backend Engineer - Data Core")
    assert [place.city for place in backend.locations] == [
        "Tallinn",
        "Vilnius",
        "Berlin",
        "Kraków",
        "Prague",
        "Bucharest",
    ]
    assert backend.employer == EmployerRef(ats="workable", board="modash", job_id="2FAA7C0BC6")
    assert sales.location.country == "CA"


def test_a_remote_job_is_open_to_the_countries_it_lists(
    source_api: SourceApi, web: WebClient
) -> None:
    backend = postings(source_api, web)[0]
    assert backend.location.workplace is Workplace.REMOTE
    assert backend.location.remote_scope == frozenset({"EE", "LT", "DE", "PL", "CZ", "RO"})
    assert backend.location.reachable_from("DE")


def test_links_dates_and_employment_are_read(source_api: SourceApi, web: WebClient) -> None:
    backend = postings(source_api, web)[0]
    assert backend.url == "https://apply.workable.com/j/2FAA7C0BC6"
    assert backend.apply_url == "https://apply.workable.com/j/2FAA7C0BC6/apply"
    assert backend.employment is Employment.FULL_TIME
    assert backend.posted_at is not None
    assert backend.posted_at.date() == date(2026, 10, 2)
    assert backend.company == "Modash"


def test_a_board_that_is_gone_makes_the_source_unavailable(
    source_api: SourceApi, web: WebClient
) -> None:
    with pytest.raises(SourceUnavailableError, match="HTTP 404"):
        WorkableFeed(web, "modash", "Modash", api=source_api(JOBS, None)).fetch()


def test_the_feed_is_named_after_its_board(web: WebClient) -> None:
    assert WorkableFeed(web, "modash", "Modash").name == "workable:modash"
