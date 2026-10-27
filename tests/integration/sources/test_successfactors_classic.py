from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from datetime import timedelta as span

import pytest

from hunter.adapters.sources.feeds.successfactors import SuccessFactorsFeed
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.posting import EmployerRef, Employment, Posting, SourceRef
from hunter.domain.pacing import Pacing, PaceRule

SourceApi = Callable[[str, str | None], str]


def jobs_of(company_id: str) -> str:
    return f"/career?company={company_id}&career_ns=job_listing_summary&resultType=XML"


def postings(source_api: SourceApi, web: WebClient, board: str, saved: str) -> list[Posting]:
    company_id = board.partition("/")[2]
    api = source_api(jobs_of(company_id), saved)
    return SuccessFactorsFeed(web, board, "The Company", api=api).fetch()


def beiersdorf(source_api: SourceApi, web: WebClient) -> list[Posting]:
    board = "career5.successfactors.eu/beiersdorfP"
    return postings(source_api, web, board, "successfactors-beiersdorf.xml")


def test_every_job_on_a_classic_portal_is_read(source_api: SourceApi, web: WebClient) -> None:
    hamburg, poznan, vienna = beiersdorf(source_api, web)
    assert hamburg.title == "Regional Material Flow Expert (all genders)"
    assert hamburg.company == "The Company"
    assert hamburg.source == SourceRef(source="successfactors", native_id="22081")
    assert hamburg.employer == EmployerRef(
        ats="successfactors", board="career5.successfactors.eu/beiersdorfP", job_id="22081"
    )
    assert hamburg.url == (
        "https://career5.successfactors.eu/career?company=beiersdorfP"
        "&career_ns=job_listing&career_job_req_id=22081"
    )
    assert hamburg.apply_url == hamburg.url
    assert "NIVEA" in hamburg.description and "<" not in hamburg.description
    assert vienna.posted_at == datetime(2026, 9, 3, tzinfo=UTC)


def test_the_place_comes_from_the_city_and_country_filters(
    source_api: SourceApi, web: WebClient
) -> None:
    hamburg, poznan, vienna = beiersdorf(source_api, web)
    assert (hamburg.location.country, hamburg.location.city) == ("DE", "Hamburg")
    assert (poznan.location.country, poznan.location.city) == ("PL", "Poznań")
    assert (vienna.location.country, vienna.location.city) == ("AT", "Vienna")


def test_the_employment_comes_from_its_filter(source_api: SourceApi, web: WebClient) -> None:
    hamburg, poznan, vienna = beiersdorf(source_api, web)
    assert (hamburg.employment, poznan.employment) == (Employment.FULL_TIME, Employment.PART_TIME)


def test_a_portal_with_a_location_and_a_volume(source_api: SourceApi, web: WebClient) -> None:
    board = "career5.successfactors.eu/WelthungerP"
    bonn, kabul, nairobi = postings(source_api, web, board, "successfactors-welthungerhilfe.xml")
    assert [job.location.country for job in (bonn, kabul, nairobi)] == ["DE", "AF", "KE"]
    assert bonn.location.city == "Bonn"
    assert bonn.employment is Employment.FULL_TIME
    assert bonn.posted_at is None
    assert "Welthungerhilfe" in bonn.description and "color" not in bonn.description


def test_nameless_elements_are_dropped_before_reading(
    source_api: SourceApi, web: WebClient
) -> None:
    """AIIB's answer holds `<>101</>`, which isn't XML."""
    board = "career2.successfactors.eu/AIIB"
    engineer, head = postings(source_api, web, board, "successfactors-aiib.xml")
    assert engineer.title == "(Senior) Digital Program Specialist - AI Model Engineer"
    assert head.title == "Head of Performance, Rewards & HR Operations"
    assert head.location.country is None
    assert head.employment is None


def test_a_wrong_company_id_makes_the_source_unavailable_but_not_gone(
    source_api: SourceApi, web: WebClient
) -> None:
    """SAP answers a company it doesn't know with 200 and an HTML page."""
    with pytest.raises(SourceUnavailableError) as raised:
        postings(source_api, web, "career5.successfactors.eu/nobody", "careers-page.html")
    assert not raised.value.gone


def test_an_answer_that_is_not_a_job_listing_is_unavailable(
    source_api: SourceApi, web: WebClient
) -> None:
    with pytest.raises(SourceUnavailableError, match="no job listing"):
        postings(source_api, web, "career5.successfactors.eu/other", "successfactors-bechtle.xml")


class Recorder(WebClient):
    """Notes the headers each read is sent with."""

    def __init__(self) -> None:
        super().__init__(Pacing({}, default=PaceRule(min_gap=span(0))), sleep=lambda _: None)
        self.sent: list[Mapping[str, str]] = []

    def get_text(
        self,
        url: str,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> str:
        self.sent.append(headers or {})
        return super().get_text(url, params, headers)


def test_a_classic_portal_is_read_as_a_browser(source_api: SourceApi) -> None:
    """SAP's robots.txt turns every bot away on its own hosts (docs/sources.md, the bot rule)."""
    recorder = Recorder()
    beiersdorf(source_api, recorder)
    (headers,) = recorder.sent
    assert "Chrome/" in headers["User-Agent"] and "Hunter" not in headers["User-Agent"]


def test_a_career_site_builder_site_is_read_as_hunter(source_api: SourceApi) -> None:
    recorder = Recorder()
    api = source_api("/sitemal.xml", "successfactors-bechtle.xml")
    SuccessFactorsFeed(recorder, "jobs.bechtle.com", "Bechtle AG", api=api).fetch()
    assert recorder.sent == [{}]
