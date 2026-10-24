from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pytest

from hunter.adapters.sources.greenhouse import GreenhouseFeed
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

JOBS = "/v1/boards/n26/jobs?content=true"
SourceApi = Callable[[str, str | None], str]


def postings(source_api: SourceApi, web: WebClient) -> list[Posting]:
    api = source_api(JOBS, "greenhouse-n26.json")
    return GreenhouseFeed(web, "n26", "N26", api=api).fetch()


def test_every_job_on_the_board_becomes_a_posting(source_api: SourceApi, web: WebClient) -> None:
    found = postings(source_api, web)
    assert [posting.title for posting in found] == [
        "Business Audit Manager",
        "IT Solutions Engineer - Google Cloud",
        "Product Manager - Investments",
    ]
    first = found[0]
    assert first.company == "N26"
    assert first.location == Location(country="DE", city="Berlin")
    assert first.source == SourceRef(source="greenhouse", native_id="8242571")
    assert first.employer == EmployerRef(ats="greenhouse", board="n26", job_id="8242571")
    assert first.url == "https://n26.com/en-eu/careers/positions/8242571?gh_jid=8242571"
    assert first.apply_url == first.url


def test_all_the_places_of_a_job_are_read(source_api: SourceApi, web: WebClient) -> None:
    several = postings(source_api, web)[1]
    assert [place.city for place in several.locations] == ["Berlin", "Vienna", "Barcelona"]


def test_descriptions_and_dates_are_read(source_api: SourceApi, web: WebClient) -> None:
    several = postings(source_api, web)[1]
    assert several.description.startswith("About the opportunity\n\nAs an IT Solutions Engineer")
    assert several.posted_at == datetime(2026, 8, 25, 3, 26, tzinfo=timezone(timedelta(hours=-4)))


def test_a_board_that_is_gone_makes_the_source_unavailable(
    source_api: SourceApi, web: WebClient
) -> None:
    api = source_api(JOBS, None)
    with pytest.raises(SourceUnavailableError, match="HTTP 404"):
        GreenhouseFeed(web, "n26", "N26", api=api).fetch()


def test_the_feed_is_named_after_its_board(web: WebClient) -> None:
    assert GreenhouseFeed(web, "n26", "N26").name == "greenhouse:n26"
