from collections.abc import Callable, Mapping
from datetime import UTC, datetime

import pytest

from hunter.adapters.sources.feeds import rexx
from hunter.adapters.sources.feeds.rexx import RexxFeed
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.boards import Board, board_from_link
from hunter.domain.discovery.posting import Employment, EmployerRef, Posting

Pages = Callable[[Mapping[str, str]], str]
LIST = "/stellenangebote.html?start=0"
ENGINEER = "/Software-Engineer-mwdiv-im-Bereich-Prototyping-Data-Analyt-de-j1026.html"
INGENIEUR = "/Software-Ingenieur-Automatisierungstechnik-mwdiv-de-j773.html"
# The saved list's job links point at the company's career domain; here they're made relative,
# so the jobs are read from the local test site.
PORTAL = {
    LIST: "rexx-ald-list.html",
    ENGINEER: "rexx-ald-job-1026.html",
    INGENIEUR: "rexx-ald-job-773.html",
}


def postings(
    source_pages: Pages, web: WebClient, saved: Mapping[str, str] = PORTAL
) -> list[Posting]:
    return RexxFeed(web, "ald", "ALD Vacuum Technologies", api=source_pages(saved)).fetch()


def test_every_job_on_the_portal_is_read_from_its_own_page(
    source_pages: Pages, web: WebClient
) -> None:
    engineer, ingenieur = postings(source_pages, web)
    assert engineer.title == "Software Engineer (m/w/div.) Additive Manufacturing & Data Analytics"
    assert engineer.company == "ALD Vacuum Technologies GmbH"
    assert engineer.employer == EmployerRef(ats="rexx", board="ald", job_id="1026")
    assert engineer.url is not None and engineer.url.endswith(ENGINEER)
    assert engineer.posted_at == datetime(2026, 10, 8, tzinfo=UTC)
    assert engineer.employment is Employment.FULL_TIME
    assert engineer.description and "<" not in engineer.description
    assert ingenieur.employer is not None and ingenieur.employer.job_id == "773"


def test_the_place_comes_from_the_job_s_address(source_pages: Pages, web: WebClient) -> None:
    engineer, _ = postings(source_pages, web)
    assert (engineer.location.country, engineer.location.city) == ("DE", "Hanau am Main")


def test_a_job_page_that_cannot_be_read_leaves_the_others(
    source_pages: Pages, web: WebClient
) -> None:
    without_one = {path: saved for path, saved in PORTAL.items() if path != INGENIEUR}
    [engineer] = postings(source_pages, web, without_one)
    assert engineer.employer is not None and engineer.employer.job_id == "1026"


def test_a_full_list_means_there_may_be_another(
    source_pages: Pages, web: WebClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second page that shows the same jobs again ends the list."""
    monkeypatch.setattr(rexx, "PAGE_SIZE", 2)
    pages = {**PORTAL, "/stellenangebote.html?start=2": "rexx-ald-list.html"}
    assert len(postings(source_pages, web, pages)) == 2


def test_a_portal_that_is_gone_makes_the_source_unavailable(
    source_pages: Pages, web: WebClient
) -> None:
    with pytest.raises(SourceUnavailableError) as raised:
        postings(source_pages, web, {})
    assert raised.value.gone


def test_a_link_to_a_rexx_portal_names_it() -> None:
    link = "https://ald-portal.rexx-recruitment.com/stellenangebote.html"
    assert board_from_link(link) == Board(ats="rexx", slug="ald")
