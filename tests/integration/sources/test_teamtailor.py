from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pytest

from hunter.adapters.sources.feeds.teamtailor import TeamtailorFeed
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import EmployerRef, Posting

JOBS = "/jobs.rss"
SourceApi = Callable[[str, str | None], str]


def postings(source_api: SourceApi, web: WebClient) -> list[Posting]:
    api = source_api(JOBS, "teamtailor-career.xml")
    return TeamtailorFeed(web, "career", "Teamtailor", api=api).fetch()


def test_every_job_in_the_feed_is_read(source_api: SourceApi, web: WebClient) -> None:
    london, stockholm = postings(source_api, web)
    assert london.title == "UK Account Executive - SMB"
    assert london.company == "Teamtailor"
    assert london.employer == EmployerRef(ats="teamtailor", board="career", job_id="8118064")
    assert london.url == "https://career.teamtailor.com/jobs/8118064-uk-account-executive-smb"
    assert london.posted_at == datetime(2026, 7, 24, 9, 5, 16, tzinfo=timezone(timedelta(hours=2)))
    assert stockholm.description


def test_places_and_workplaces_come_from_the_feed(source_api: SourceApi, web: WebClient) -> None:
    london, stockholm = postings(source_api, web)
    assert london.location == Location(country="GB", city="London", workplace=Workplace.HYBRID)
    assert stockholm.location == Location(
        country="SE", city="Stockholm", workplace=Workplace.ONSITE
    )


def test_a_feed_that_is_gone_makes_the_source_unavailable(
    source_api: SourceApi, web: WebClient
) -> None:
    with pytest.raises(SourceUnavailableError, match="HTTP 404"):
        TeamtailorFeed(web, "career", "Teamtailor", api=source_api(JOBS, None)).fetch()


def test_the_feed_is_named_after_its_board(web: WebClient) -> None:
    feed = TeamtailorFeed(web, "career", "Teamtailor")
    assert (feed.name, feed.api) == ("teamtailor:career", "https://career.teamtailor.com")
