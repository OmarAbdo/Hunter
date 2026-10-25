from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from hunter.adapters.sources.feeds.dvinci import DvinciFeed
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.boards import Board, board_from_link
from hunter.domain.discovery.posting import EmployerRef, Posting

JOBS = "/jobPublication/list.json"
SourceApi = Callable[[str, str | None], str]


def postings(source_api: SourceApi, web: WebClient) -> list[Posting]:
    api = source_api(JOBS, "dvinci-portals.json")
    return DvinciFeed(web, "mtuaero", "MTU Aero Engines", api=api).fetch()


def test_every_job_on_the_portal_is_read(source_api: SourceApi, web: WebClient) -> None:
    hamburg, emosys, _ = postings(source_api, web)
    assert hamburg.title.startswith("Elektroniker für Automatisierungs- und Systemtechnik")
    assert hamburg.employer == EmployerRef(ats="dvinci", board="mtuaero", job_id="79768")
    assert hamburg.url is not None and "/jobs/63195/" in hamburg.url
    assert hamburg.apply_url == "https://mtuaero.dvinci-easy.com/de/jobs/63195/apply"
    assert hamburg.posted_at == datetime(2026, 8, 13, 6, 21, 13, 86000, tzinfo=UTC)
    assert hamburg.description


def test_the_company_is_the_one_the_job_names(source_api: SourceApi, web: WebClient) -> None:
    """One portal can hold several companies of a group; a job that names none is the board's."""
    hamburg, emosys, primas = postings(source_api, web)
    assert (hamburg.company, emosys.company) == ("MTU Aero Engines", "eMoSys GmbH")
    assert primas.company == "PrimAs Tiefkühlprodukte GmbH"


def test_every_place_of_a_job_is_kept(source_api: SourceApi, web: WebClient) -> None:
    hamburg, emosys, primas = postings(source_api, web)
    assert (hamburg.location.country, hamburg.location.city) == ("DE", "Hamburg")
    assert [place.country for place in emosys.locations] == ["DE", "DE"]
    assert emosys.location.city == "Munich"
    assert primas.location.country == "AT"


def test_an_opening_advertised_twice_is_one_job(source_api: SourceApi, web: WebClient) -> None:
    """d.vinci can publish one opening in several ads; the first one stands for it."""
    *_, primas = postings(source_api, web)
    assert primas.title == "Anlagenbediener:in"
    assert len(postings(source_api, web)) == 3


def test_a_portal_that_is_gone_makes_the_source_unavailable(
    source_api: SourceApi, web: WebClient
) -> None:
    with pytest.raises(SourceUnavailableError) as raised:
        DvinciFeed(web, "gone", "Gone", api=source_api(JOBS, None)).fetch()
    assert raised.value.gone


def test_a_job_link_names_the_portal() -> None:
    link = "https://zott-karriere.dvinci-easy.com/de/jobs/22008/anlagenfuehrer"
    assert board_from_link(link) == Board(ats="dvinci", slug="zott-karriere")
