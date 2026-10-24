from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from hunter.adapters.sources.recruitee import RecruiteeFeed
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import EmployerRef, Employment, Posting

OFFERS = "/api/offers/"
SourceApi = Callable[[str, str | None], str]


def postings(source_api: SourceApi, web: WebClient) -> list[Posting]:
    api = source_api(OFFERS, "recruitee-tellent.json")
    return RecruiteeFeed(web, "jobs", "Tellent", api=api).fetch()


def test_every_offer_is_read(source_api: SourceApi, web: WebClient) -> None:
    hybrid, remote = postings(source_api, web)
    assert hybrid.title == "Strategic Account Manager - Benelux"
    assert hybrid.company == "Tellent"
    assert hybrid.employer == EmployerRef(ats="recruitee", board="jobs", job_id="2771339")
    assert hybrid.url == "https://careers.tellent.com/o/strategic-account-manager-benelux-1"
    assert hybrid.employment is Employment.FULL_TIME
    assert hybrid.posted_at == datetime(2026, 10, 5, 13, 25, 3, tzinfo=UTC)
    assert remote.description


def test_workplaces_come_from_the_offer_flags(source_api: SourceApi, web: WebClient) -> None:
    hybrid, remote = postings(source_api, web)
    assert hybrid.location == Location(country="NL", city="Amsterdam", workplace=Workplace.HYBRID)
    assert remote.location == Location(
        country="NL", city="Amsterdam", workplace=Workplace.REMOTE, remote_scope=frozenset({"NL"})
    )


def test_a_board_that_is_gone_makes_the_source_unavailable(
    source_api: SourceApi, web: WebClient
) -> None:
    with pytest.raises(SourceUnavailableError, match="HTTP 404"):
        RecruiteeFeed(web, "jobs", "Tellent", api=source_api(OFFERS, None)).fetch()


def test_the_feed_is_named_after_its_board(web: WebClient) -> None:
    assert RecruiteeFeed(web, "jobs", "Tellent").name == "recruitee:jobs"
