from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pytest

from hunter.adapters.sources.feeds.coveto import CovetoFeed
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.boards import Board, board_from_link
from hunter.domain.discovery.posting import EmployerRef, Posting

JOBS = "/public/rss/"
SourceApi = Callable[[str, str | None], str]


def postings(source_api: SourceApi, web: WebClient) -> list[Posting]:
    api = source_api(JOBS, "coveto-empiricus.xml")
    return CovetoFeed(web, "k11145", "empiricus GmbH", api=api).fetch()


def test_every_job_in_the_feed_is_read(source_api: SourceApi, web: WebClient) -> None:
    mainz, frankfurt, mannheim = postings(source_api, web)
    assert (mainz.title, mainz.company) == ("IT Projekt Manager/in (m/w/d)", "empiricus GmbH")
    assert mainz.employer == EmployerRef(ats="coveto", board="k11145", job_id="3943")
    assert (
        mainz.url
        == "https://job-portal.empiricus.eu/job-it-projekt-manager-in-m-w-d-mainz-3943.html"
    )
    assert mainz.posted_at == datetime(
        2026, 10, 13, 15, 41, 34, tzinfo=timezone(timedelta(hours=2))
    )
    assert mannheim.title == "Recruiter/in (m/w/d) in der IT-Personalberatung"


def test_the_place_is_the_one_the_job_names(source_api: SourceApi, web: WebClient) -> None:
    mainz, frankfurt, _ = postings(source_api, web)
    assert (mainz.location.country, mainz.location.city) == ("DE", "Mainz")
    assert frankfurt.location.city == "Frankfurt am Main"


def test_a_feed_that_is_gone_makes_the_source_unavailable(
    source_api: SourceApi, web: WebClient
) -> None:
    with pytest.raises(SourceUnavailableError) as raised:
        CovetoFeed(web, "k0", "Gone", api=source_api(JOBS, None)).fetch()
    assert raised.value.gone


def test_a_link_to_a_coveto_portal_names_its_board() -> None:
    assert board_from_link("https://k11145.coveto.de/public/rss/") == Board("coveto", "k11145")
