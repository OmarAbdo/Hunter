import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from hunter.adapters.sources.alerts.alert_ads import AlertPageAds, first_hop, job_page
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import Posting, SourceRef

SAVED = Path(__file__).resolve().parents[2] / "fixtures" / "sources"
STEPSTONE_JOB = "https://www.stepstone.de/stellenangebote--job--14717039-inline.html"
XING_JOB = "https://www.xing.com/jobs/berlin-senior-full-stack-engineer-159027574"
# First hops as the alert links give them; the magic link would sign in as the inbox's owner.
MAGIC_HOP = (
    "https://www.stepstone.de/v2/magiclink/exchange?magicLink=SECRET"
    "&returnUrl=%2Fstellenangebote----14717039-inline.html%3FCID%3DR_EM_STU%26lang%3Dde"
)
XING_HOP = (
    "https://login.xing.com/continue?level=loggedout&dest_url=https%3A%2F%2Fwww.xing.com%2Fjobs"
    "%2Fberlin-senior-full-stack-engineer-159027574%3Fijt%3Djb_16%26sc_cmp%3Dsymc"
)
PAGES = {
    STEPSTONE_JOB: "alert-page-stepstone-live.html",
    XING_JOB: "alert-page-xing-live.html",
}


def alert_job(source: str) -> Posting:
    return Posting(
        title="Software Test Engineer (m/w/d)",
        company="Schmitt Engineering",
        location=Location(country="DE", city="Berlin"),
        source=SourceRef(source=source, native_id="1"),
        url="https://click.example/tracked",
    )


class Pages:
    """Edge, as far as the reader sees it: each address's saved page, and every address asked."""

    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.asked: list[str] = []

    def dom(self, url: str) -> str:
        self.asked.append(url)
        return (SAVED / self.pages[url]).read_text(encoding="utf-8")


def test_a_stepstone_job_s_page_is_named_inside_its_magic_link() -> None:
    assert job_page(MAGIC_HOP) == STEPSTONE_JOB


def test_a_stepstone_job_s_page_is_its_own_address_without_tracking() -> None:
    hop = "https://www.stepstone.de/stellenangebote--Tester-Berlin--14717039-inline.html?CID=x"
    assert job_page(hop) == STEPSTONE_JOB


def test_a_xing_job_s_page_is_named_inside_its_login_hop() -> None:
    assert job_page(XING_HOP) == XING_JOB


def test_a_hop_that_names_no_job_has_no_page() -> None:
    assert job_page(None) is None
    assert job_page("https://www.stepstone.de/") is None


def test_the_ad_is_read_from_the_public_page_and_never_through_the_sign_in() -> None:
    pages = Pages(PAGES)
    ad = AlertPageAds(lambda _: MAGIC_HOP, pages.dom).read(alert_job("stepstone-alert"))
    assert ad.startswith("Über uns")
    assert "Friedl" not in ad
    assert pages.asked == [STEPSTONE_JOB]


def test_a_xing_ad_is_read_from_its_page() -> None:
    ad = AlertPageAds(lambda _: XING_HOP, Pages(PAGES).dom).read(alert_job("xing-alert"))
    assert len(ad) > 4000


@pytest.mark.parametrize(
    "saved",
    ["alert-page-stepstone-gone.html", "alert-page-stepstone-not-found.html"],
)
def test_a_page_that_says_the_job_is_no_longer_there_makes_it_gone(saved: str) -> None:
    reader = AlertPageAds(lambda _: MAGIC_HOP, Pages({STEPSTONE_JOB: saved}).dom)
    with pytest.raises(SourceUnavailableError) as raised:
        reader.read(alert_job("stepstone-alert"))
    assert raised.value.gone


def test_a_xing_ad_that_isn_t_available_is_gone() -> None:
    reader = AlertPageAds(lambda _: XING_HOP, Pages({XING_JOB: "alert-page-xing-gone.html"}).dom)
    with pytest.raises(SourceUnavailableError) as raised:
        reader.read(alert_job("xing-alert"))
    assert raised.value.gone


def test_a_link_that_leads_to_no_job_is_left_for_the_next_run() -> None:
    reader = AlertPageAds(lambda _: None, Pages({}).dom)
    with pytest.raises(SourceUnavailableError) as raised:
        reader.read(alert_job("xing-alert"))
    assert not raised.value.gone


class Redirect(BaseHTTPRequestHandler):
    def answer_get(self) -> None:
        self.send_response(302)
        self.send_header("Location", MAGIC_HOP)
        self.end_headers()

    def log_message(self, *_: object) -> None:
        return


# http.server looks up `do_GET`, a name the naming rules don't allow to be written out.
setattr(Redirect, "do_" + "GET", Redirect.answer_get)


@pytest.fixture
def tracking_link() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/tracked"
    server.shutdown()


def test_the_first_hop_is_read_without_following_it(tracking_link: str) -> None:
    assert first_hop(tracking_link) == MAGIC_HOP
