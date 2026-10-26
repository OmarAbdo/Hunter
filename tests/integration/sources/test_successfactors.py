from collections.abc import Callable

import pytest

from hunter.adapters.sources.feeds.successfactors import SuccessFactorsFeed
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.boards import Board, board_from_link
from hunter.domain.discovery.posting import EmployerRef, Posting

JOBS = "/sitemal.xml"
SourceApi = Callable[[str, str | None], str]


def postings(source_api: SourceApi, web: WebClient) -> list[Posting]:
    api = source_api(JOBS, "successfactors-bechtle.xml")
    return SuccessFactorsFeed(web, "jobs.bechtle.com", "Bechtle AG", api=api).fetch()


def test_every_job_on_the_career_site_is_read(source_api: SourceApi, web: WebClient) -> None:
    budapest, eindhoven, neckarsulm = postings(source_api, web)
    assert neckarsulm.title == "Teamleiter Vertrieb Public (w/m/d)"  # without its place
    assert neckarsulm.company == "Bechtle"
    assert neckarsulm.employer is not None
    assert neckarsulm.employer.board == "jobs.bechtle.com"
    assert budapest.employer == EmployerRef(
        ats="successfactors", board="jobs.bechtle.com", job_id="1329359557"
    )
    assert budapest.url == (
        "https://jobs.bechtle.com/hu/job/Budapest-Senior-SAP-Consultant-%28SAP-Basis%29-1037/"
        "1329359557/"
    )
    assert "SAP" in budapest.description and "<" not in budapest.description


def test_the_place_comes_from_the_job_s_location(source_api: SourceApi, web: WebClient) -> None:
    budapest, eindhoven, neckarsulm = postings(source_api, web)
    assert (budapest.location.country, budapest.location.city) == ("HU", "Budapest")
    assert (eindhoven.location.country, eindhoven.location.city) == ("NL", "Eindhoven")
    assert neckarsulm.location.country == "DE"


def test_a_site_without_the_feed_makes_the_source_unavailable(
    source_api: SourceApi, web: WebClient
) -> None:
    with pytest.raises(SourceUnavailableError) as raised:
        SuccessFactorsFeed(web, "jobs.example.com", "Example", api=source_api(JOBS, None)).fetch()
    assert raised.value.gone


def test_a_job_link_on_a_career_site_names_its_host() -> None:
    link = "https://jobs.bechtle.com/job/Neckarsulm-Teamleiter-Vertrieb-Public-74172/1312345601/"
    assert board_from_link(link) == Board(ats="successfactors", slug="jobs.bechtle.com")
    localised = "https://jobs.bechtle.com/hu/job/Budapest-Senior-SAP-Consultant-1037/1329359557/"
    assert board_from_link(localised) == Board(ats="successfactors", slug="jobs.bechtle.com")


def test_other_systems_job_links_are_not_taken_for_a_career_site() -> None:
    assert board_from_link("https://zvoove.jobs.personio.de/job/1234567") == Board(
        "personio", "zvoove.de"
    )
    softgarden = "https://andrena.softgarden.io/job/62479624/Softwareentwickler-Java-w-m-d-"
    assert board_from_link(softgarden) == Board("softgarden", "andrena")


def test_a_newer_job_link_on_a_career_site_names_its_host() -> None:
    """Bundesdruckerei's career site links jobs as `/job/<title>/<number>-<locale>`."""
    link = "https://jobs.bundesdruckerei.de/job/devops-engineer-im-bereich-digitale-identitaten-m-w-d/761-de_DE"
    assert board_from_link(link) == Board(ats="successfactors", slug="jobs.bundesdruckerei.de")
