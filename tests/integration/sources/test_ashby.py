from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from hunter.adapters.sources.ashby import AshbyFeed
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import EmployerRef, Employment, Posting

JOBS = "/posting-api/job-board/enpal?includeCompensation=true"
SourceApi = Callable[[str, str | None], str]


def postings(source_api: SourceApi, web: WebClient) -> list[Posting]:
    api = source_api(JOBS, "ashby-enpal.json")
    return AshbyFeed(web, "enpal", "Enpal", api=api).fetch()


def test_listed_jobs_become_postings(source_api: SourceApi, web: WebClient) -> None:
    found = postings(source_api, web)
    assert len(found) == 5
    assert "Unlisted test copy" not in [posting.title for posting in found]
    first = found[0]
    job_id = first.source.native_id
    assert (first.company, first.source.source, job_id[:8]) == ("Enpal", "ashby", "7b8573da")
    assert first.employer == EmployerRef(ats="ashby", board="enpal", job_id=job_id)
    assert first.url == f"https://jobs.ashbyhq.com/enpal/{job_id}"
    assert first.apply_url == f"https://jobs.ashbyhq.com/enpal/{job_id}/application"


def test_places_come_from_the_address(source_api: SourceApi, web: WebClient) -> None:
    berlin, tunis = postings(source_api, web)[:2]
    assert berlin.location == Location(country="DE", city="Berlin")
    assert tunis.location == Location(country="TN", city="Tunis", workplace=Workplace.ONSITE)


def test_a_remote_job_is_open_to_its_country(source_api: SourceApi, web: WebClient) -> None:
    remote = postings(source_api, web)[3]
    assert remote.location == Location(
        country="DE", workplace=Workplace.REMOTE, remote_scope=frozenset({"DE"})
    )
    assert [place.city for place in remote.other_locations][:2] == ["Bonn", "Frankfurt am Main"]


def test_employment_types_dates_and_descriptions_are_read(
    source_api: SourceApi, web: WebClient
) -> None:
    found = postings(source_api, web)
    assert found[0].employment is Employment.FULL_TIME
    assert found[4].employment is Employment.INTERNSHIP
    assert found[3].posted_at == datetime(2026, 8, 13, 10, 31, 57, 196000, tzinfo=UTC)
    assert found[3].description


def test_a_board_that_is_gone_makes_the_source_unavailable(
    source_api: SourceApi, web: WebClient
) -> None:
    api = source_api(JOBS, None)
    with pytest.raises(SourceUnavailableError, match="HTTP 404"):
        AshbyFeed(web, "enpal", "Enpal", api=api).fetch()


def test_the_feed_is_named_after_its_board(web: WebClient) -> None:
    assert AshbyFeed(web, "enpal", "Enpal").name == "ashby:enpal"
