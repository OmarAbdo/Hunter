from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from hunter.adapters.sources.lever import LeverFeed
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import EmployerRef, Employment, Posting

POSTINGS = "/v0/postings/unzer?mode=json"
SourceApi = Callable[[str, str | None], str]


def postings(source_api: SourceApi, web: WebClient) -> list[Posting]:
    api = source_api(POSTINGS, "lever-unzer.json")
    return LeverFeed(web, "unzer", "Unzer", api=api).fetch()


def test_every_posting_on_the_board_is_read(source_api: SourceApi, web: WebClient) -> None:
    berlin, munsbach = postings(source_api, web)
    job_id = "b2fb123c-5e82-407c-8a8b-8f33094c898a"
    assert berlin.title.startswith("(Senior) Software Engineer - Microsoft Dynamics 365")
    assert (berlin.company, berlin.employment) == ("Unzer", Employment.FULL_TIME)
    assert berlin.employer == EmployerRef(ats="lever", board="unzer", job_id=job_id)
    assert berlin.url == f"https://jobs.eu.lever.co/unzer/{job_id}"
    assert berlin.apply_url == f"https://jobs.eu.lever.co/unzer/{job_id}/apply"
    assert berlin.posted_at == datetime.fromtimestamp(1792758322.868, UTC)
    assert munsbach.location.country == "LU"


def test_places_come_from_the_location_and_country(source_api: SourceApi, web: WebClient) -> None:
    berlin = postings(source_api, web)[0]
    assert berlin.location == Location(country="DE", city="Berlin", workplace=Workplace.HYBRID)
    assert berlin.description


def test_a_board_hosted_in_the_eu_is_found_there(source_api: SourceApi, web: WebClient) -> None:
    us_api = source_api(POSTINGS, None)
    eu_api = source_api(POSTINGS, "lever-unzer.json")
    assert len(LeverFeed(web, "unzer", "Unzer", api=(us_api, eu_api)).fetch()) == 2


def test_a_board_on_neither_host_makes_the_source_unavailable(
    source_api: SourceApi, web: WebClient
) -> None:
    gone = source_api(POSTINGS, None)
    with pytest.raises(SourceUnavailableError, match="HTTP 404"):
        LeverFeed(web, "unzer", "Unzer", api=(gone, gone)).fetch()


def test_the_feed_is_named_after_its_board(web: WebClient) -> None:
    assert LeverFeed(web, "unzer", "Unzer").name == "lever:unzer"
