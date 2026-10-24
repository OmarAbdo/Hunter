from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from hunter.adapters.sources.personio import PersonioFeed
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import EmployerRef, Employment, Posting

POSITIONS = "/xml?language=en"
SourceApi = Callable[[str, str | None], str]


def postings(source_api: SourceApi, web: WebClient) -> list[Posting]:
    api = source_api(POSITIONS, "personio-zvoove.xml")
    return PersonioFeed(web, "zvoove.de", "zvoove", api=api).fetch()


def test_every_position_is_read(source_api: SourceApi, web: WebClient) -> None:
    engineer = postings(source_api, web)[0]
    assert engineer.title == "(Senior) Software Engineer (m/f/d) - AI-First Development"
    assert engineer.company == "zvoove Software Germany GmbH"
    assert engineer.employer == EmployerRef(ats="personio", board="zvoove.de", job_id="2825784")
    assert engineer.url == "https://zvoove.jobs.personio.de/job/2825784"
    assert engineer.apply_url == "https://zvoove.jobs.personio.de/job/2825784#apply"
    assert engineer.posted_at == datetime(2026, 10, 2, 16, 20, 8, tzinfo=UTC)
    assert engineer.description.startswith("Job description\n\nAs a Senior Software Engineer")


def test_a_remote_office_makes_the_job_remote_in_the_other_offices_countries(
    source_api: SourceApi, web: WebClient
) -> None:
    engineer, vienna = postings(source_api, web)[:2]
    assert engineer.location == Location(
        country="DE", city="Munich", workplace=Workplace.REMOTE, remote_scope=frozenset({"DE"})
    )
    assert vienna.location.remote_scope == frozenset({"AT"})


def test_offices_read_as_country_and_city(source_api: SourceApi, web: WebClient) -> None:
    lohne, amersfoort = postings(source_api, web)[2:]
    assert lohne.location.country == "DE"
    assert amersfoort.location == Location(country="NL", city="Amersfoort")


def test_employment_comes_from_type_and_schedule(source_api: SourceApi, web: WebClient) -> None:
    engineer, _, _, amersfoort = postings(source_api, web)
    assert engineer.employment is Employment.FULL_TIME
    assert amersfoort.employment is Employment.TEMPORARY


def test_a_board_that_is_gone_makes_the_source_unavailable(
    source_api: SourceApi, web: WebClient
) -> None:
    with pytest.raises(SourceUnavailableError, match="HTTP 404"):
        PersonioFeed(web, "zvoove.de", "zvoove", api=source_api(POSITIONS, None)).fetch()


def test_the_feed_is_named_after_its_board_on_its_domain(web: WebClient) -> None:
    feed = PersonioFeed(web, "zvoove.de", "zvoove")
    assert (feed.name, feed.api) == ("personio:zvoove.de", "https://zvoove.jobs.personio.de")
