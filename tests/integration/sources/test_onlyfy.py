from collections.abc import Callable, Mapping
from datetime import UTC, datetime

import pytest

from hunter.adapters.sources.feeds import onlyfy
from hunter.adapters.sources.feeds.onlyfy import OnlyfyFeed
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.boards import Board, board_from_link
from hunter.domain.discovery.posting import Employment, EmployerRef, Posting

Pages = Callable[[Mapping[str, str]], str]
SAVED = "onlyfy-magenta.html"


def postings(source_pages: Pages, web: WebClient) -> list[Posting]:
    api = source_pages({"/?page=1": SAVED})
    return OnlyfyFeed(web, "magenta", "Magenta Telekom", api=api).fetch()


def test_every_job_on_the_board_is_read(source_pages: Pages, web: WebClient) -> None:
    sales, provisioning, intern = postings(source_pages, web)
    assert sales.title == "Regional Sales Manager (w/m/d) Field & Fiber Sales NÖ Nord"
    assert sales.company == "Magenta Telekom"
    assert sales.employer == EmployerRef(
        ats="onlyfy", board="magenta", job_id="cg730lwfbz2qn9j3r65e7xlmu15elkj"
    )
    assert sales.url is not None and sales.url.endswith("/en/job/cg730lwfbz2qn9j3r65e7xlmu15elkj")
    assert sales.posted_at == datetime(2026, 10, 14, tzinfo=UTC)
    assert intern.title.startswith("Praktikant:in (w/m/d) Customer Insights")


def test_the_place_and_employment_come_from_the_job_s_line(
    source_pages: Pages, web: WebClient
) -> None:
    sales, provisioning, intern = postings(source_pages, web)
    assert (sales.location.country, sales.location.city) == ("AT", "Vienna")
    assert provisioning.location.city == "Graz"
    assert sales.employment is Employment.FULL_TIME
    assert intern.employment is Employment.PART_TIME


def test_a_full_page_means_there_may_be_another(
    source_pages: Pages, web: WebClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(onlyfy, "PAGE_SIZE", 3)
    api = source_pages({"/?page=1": SAVED, "/?page=2": "onlyfy-magenta-2.html"})
    jobs = OnlyfyFeed(web, "magenta", "Magenta Telekom", api=api).fetch()
    assert len(jobs) == 5
    assert jobs[3].employer is not None
    assert jobs[3].employer.job_id == "q56jd4h9ix6mqkd1jrdcdy8ic4jjafj"  # without the page query


def test_a_page_of_jobs_already_read_ends_the_list(
    source_pages: Pages, web: WebClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A board with one page shows that page again for every page number after it."""
    monkeypatch.setattr(onlyfy, "PAGE_SIZE", 3)
    api = source_pages({"/?page=1": SAVED, "/?page=2": SAVED})
    assert len(OnlyfyFeed(web, "magenta", "Magenta Telekom", api=api).fetch()) == 3


def test_a_board_that_is_gone_makes_the_source_unavailable(
    source_pages: Pages, web: WebClient
) -> None:
    with pytest.raises(SourceUnavailableError) as raised:
        OnlyfyFeed(web, "gone", "Gone", api=source_pages({})).fetch()
    assert raised.value.gone


def test_a_job_link_names_the_board() -> None:
    link = "https://admiral.onlyfy.jobs/job/4qyiv1l9wc2xp7hfqkyje4b8tn7uq5"
    assert board_from_link(link) == Board(ats="onlyfy", slug="admiral")
