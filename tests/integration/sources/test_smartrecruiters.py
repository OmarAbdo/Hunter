from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from hunter.adapters.sources.smartrecruiters import SmartRecruitersFeed
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import EmployerRef, Employment, Posting

POSTINGS = "/v1/companies/Brainlab/postings?limit=100&offset=0"
SourceApi = Callable[[str, str | None], str]


def postings(source_api: SourceApi, web: WebClient) -> list[Posting]:
    api = source_api(POSTINGS, "smartrecruiters-brainlab.json")
    return SmartRecruitersFeed(web, "Brainlab", "Brainlab", api=api).fetch()


def test_every_posting_is_read(source_api: SourceApi, web: WebClient) -> None:
    student, houston, sales = postings(source_api, web)
    job_id = "744000157393689"
    assert student.title == "Werkstudent:in Event Management"
    assert student.company == "Brainlab"
    assert student.employer == EmployerRef(ats="smartrecruiters", board="Brainlab", job_id=job_id)
    assert student.url == f"https://jobs.smartrecruiters.com/Brainlab/{job_id}"
    assert student.posted_at == datetime(2026, 10, 23, 6, 48, 23, 435000, tzinfo=UTC)
    assert houston.location.country == "US"


def test_places_and_workplaces_come_from_the_location(
    source_api: SourceApi, web: WebClient
) -> None:
    student, _, sales = postings(source_api, web)
    assert student.location == Location(country="DE", city="Munich")
    assert sales.location == Location(country="DE", city="Munich", workplace=Workplace.HYBRID)


def test_employment_types_are_read(source_api: SourceApi, web: WebClient) -> None:
    student, houston, _ = postings(source_api, web)
    assert student.employment is Employment.INTERNSHIP
    assert houston.employment is Employment.FULL_TIME


def test_a_board_that_is_gone_makes_the_source_unavailable(
    source_api: SourceApi, web: WebClient
) -> None:
    with pytest.raises(SourceUnavailableError, match="HTTP 404"):
        SmartRecruitersFeed(web, "Brainlab", "Brainlab", api=source_api(POSTINGS, None)).fetch()


def test_the_feed_is_named_after_its_board(web: WebClient) -> None:
    assert SmartRecruitersFeed(web, "Brainlab", "Brainlab").name == "smartrecruiters:Brainlab"
