from collections.abc import Callable, Mapping
from datetime import UTC, datetime

import pytest

from hunter.adapters.sources.searches import jooble
from hunter.adapters.sources.searches.jooble import JoobleSearch, search_body
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.campaign import Search
from hunter.domain.discovery.posting import Employment, Posting

Pages = Callable[[Mapping[str, str]], str]
BERLIN = Search(source="jooble", query="software engineer", place="Berlin", country="DE")
KEY = {"api_key": "the-key"}
SAVED = "jooble-berlin.json"


def postings(source_pages: Pages, web: WebClient) -> list[Posting]:
    return JoobleSearch(web, BERLIN, KEY, api=source_pages({"/the-key": SAVED})).fetch()


def test_a_search_brings_the_jobs_it_finds(source_pages: Pages, web: WebClient) -> None:
    humanity, cello, augustus = postings(source_pages, web)
    assert (humanity.title, humanity.company) == (
        "Software Engineer, ML Ops and Platform",
        "Tools for Humanity",
    )
    assert humanity.source.native_id == "-1044658708616374353"
    assert humanity.url == "https://jooble.org/desc/-1044658708616374353"  # without tracking
    assert humanity.employment is Employment.FULL_TIME
    assert cello.posted_at == datetime(2026, 10, 17, 14, 6, 0, 117000, tzinfo=UTC)
    assert "<" not in humanity.description and "&nbsp;" not in humanity.description
    assert augustus.title == "(Senior) Software Engineer"


def test_a_job_placed_only_in_a_country_has_no_town(source_pages: Pages, web: WebClient) -> None:
    humanity, *_ = postings(source_pages, web)
    assert (humanity.location.country, humanity.location.city) == ("DE", None)


def test_the_search_asks_for_its_query_place_and_page() -> None:
    assert search_body(BERLIN, page=2) == {
        "keywords": "software engineer",
        "location": "Berlin",
        "page": "2",
    }


def test_a_full_page_means_there_may_be_another_up_to_the_most_pages(
    source_pages: Pages, web: WebClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every page is asked for at the same address; the test site answers each with the same."""
    monkeypatch.setattr(jooble, "PAGE_SIZE", 3)
    monkeypatch.setattr(jooble, "MOST_PAGES", 2)
    assert len(postings(source_pages, web)) == 3  # the same jobs again end the search


def test_a_search_is_named_by_its_query_place_and_country(web: WebClient) -> None:
    assert JoobleSearch(web, BERLIN, KEY).name == "jooble:software engineer@Berlin,DE"


def test_a_failed_search_never_shows_the_key(source_pages: Pages, web: WebClient) -> None:
    """Errors are printed in a run's report; the key is in the address Jooble is asked at."""
    with pytest.raises(SourceUnavailableError) as raised:
        JoobleSearch(web, BERLIN, KEY, api=source_pages({})).fetch()
    assert "the-key" not in str(raised.value)
