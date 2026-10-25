from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from hunter.adapters.sources.feeds.softgarden import SoftgardenFeed
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.boards import Board, board_from_link
from hunter.domain.discovery.posting import EmployerRef, Posting

JOBS = "/de/vacancies"
SourceApi = Callable[[str, str | None], str]


def postings(source_api: SourceApi, web: WebClient, saved: str, board: str) -> list[Posting]:
    return SoftgardenFeed(web, board, board.title(), api=source_api(JOBS, saved)).fetch()


def test_every_job_on_the_board_is_read(source_api: SourceApi, web: WebClient) -> None:
    berlin, lubeck = postings(source_api, web, "softgarden-hypoport.html", "hypoport")
    assert berlin.title == "Spezialist für Baufinanzierung (m/w/d)"
    assert berlin.employer == EmployerRef(ats="softgarden", board="hypoport", job_id="56886158")
    assert berlin.url is not None and berlin.url.endswith(
        "/job/56886158/Spezialist-f%C3%BCr-Baufinanzierung-m-w-d-?jobDbPVId=288604248&l=de"
    )
    assert berlin.posted_at == datetime(2026, 10, 23, tzinfo=UTC)
    assert lubeck.title.startswith("Immobilienbesichtiger:in")


def test_a_group_s_board_names_each_job_s_company(source_api: SourceApi, web: WebClient) -> None:
    berlin, lubeck = postings(source_api, web, "softgarden-hypoport.html", "hypoport")
    assert berlin.company == "Dr. Klein Privatkunden AG – Franchisevertrieb"
    assert lubeck.company == "Value AG the valuation group"


def test_every_place_of_a_job_is_kept(source_api: SourceApi, web: WebClient) -> None:
    berlin, lubeck = postings(source_api, web, "softgarden-hypoport.html", "hypoport")
    assert (berlin.location.country, berlin.location.city) == ("DE", "Berlin")
    assert [place.city for place in lubeck.locations][1] == "Lübeck"
    assert len(lubeck.locations) == 3


def test_a_board_that_shows_no_places_gives_jobs_without_one(
    source_api: SourceApi, web: WebClient
) -> None:
    [partner] = postings(source_api, web, "softgarden-inform.html", "inform-software")
    assert partner.company == "Inform-Software"
    assert partner.location.city is None


def test_a_board_that_is_gone_makes_the_source_unavailable(
    source_api: SourceApi, web: WebClient
) -> None:
    with pytest.raises(SourceUnavailableError) as raised:
        SoftgardenFeed(web, "gone", "Gone", api=source_api(JOBS, None)).fetch()
    assert raised.value.gone


def test_a_job_link_names_the_board() -> None:
    link = "https://andrena.softgarden.io/job/62479624/Softwareentwickler-Java-w-m-d-"
    assert board_from_link(link) == Board(ats="softgarden", slug="andrena")
