from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from urllib.parse import urlencode

import pytest

from hunter.adapters.sources.searches import adzuna
from hunter.adapters.sources.searches.adzuna import AdzunaSearch
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.campaign import Search
from hunter.domain.discovery.posting import Employment, Posting

Pages = Callable[[Mapping[str, str]], str]
BERLIN = Search(source="adzuna", query="software engineer", place="Berlin", country="DE")
KEY = {"app_id": "app-id", "app_key": "app-key"}
SAVED = "adzuna-de-berlin.json"


def page_path(page: int, size: int = 50) -> str:
    params = {"app_id": "app-id", "app_key": "app-key", "results_per_page": str(size)}
    search = {"what": "software engineer", "where": "Berlin", "max_days_old": "30"}
    return (
        f"/de/search/{page}?{urlencode({**params, **search, 'content-type': 'application/json'})}"
    )


def postings(source_pages: Pages, web: WebClient) -> list[Posting]:
    return AdzunaSearch(web, BERLIN, KEY, api=source_pages({page_path(1): SAVED})).fetch()


def test_a_search_brings_the_jobs_it_finds(source_pages: Pages, web: WebClient) -> None:
    instaffo, noir, riverty = postings(source_pages, web)
    assert (instaffo.title, instaffo.company) == (
        "Senior AI Software Engineer (all genders) in Berlin",
        "Instaffo GmbH",
    )
    assert instaffo.source.native_id == "5940418543"
    assert instaffo.url == "https://www.adzuna.de/land/ad/5940418543"  # without tracking
    assert instaffo.posted_at == datetime(2026, 10, 24, 13, 38, 11, tzinfo=UTC)
    assert noir.employment is Employment.FULL_TIME
    assert riverty.employment is None


def test_the_place_is_the_first_area_that_names_a_town(
    source_pages: Pages, web: WebClient
) -> None:
    """Adzuna gives areas from the country down: Deutschland, Berlin, Mitte. Mitte is a town in
    GeoNames too, but the job is in Berlin."""
    instaffo, noir, _ = postings(source_pages, web)
    assert (instaffo.location.country, instaffo.location.city) == ("DE", "Berlin")
    assert (noir.location.country, noir.location.city) == ("DE", "Berlin")


def test_a_full_page_means_there_may_be_another_up_to_the_most_pages(
    source_pages: Pages, web: WebClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(adzuna, "PAGE_SIZE", 3)
    monkeypatch.setattr(adzuna, "MOST_PAGES", 2)
    api = source_pages({page_path(1, 3): SAVED, page_path(2, 3): SAVED})
    assert len(AdzunaSearch(web, BERLIN, KEY, api=api).fetch()) == 6


def test_a_search_without_a_country_is_refused(web: WebClient) -> None:
    anywhere = Search(source="adzuna", query="software engineer")
    with pytest.raises(SourceUnavailableError, match="needs a country"):
        AdzunaSearch(web, anywhere, KEY).fetch()


def test_a_search_is_named_by_its_query_place_and_country(web: WebClient) -> None:
    assert AdzunaSearch(web, BERLIN, KEY).name == "adzuna:software engineer@Berlin,DE"


def test_a_failed_search_never_shows_the_key(source_pages: Pages, web: WebClient) -> None:
    """Errors are printed in a run's report; the keys are in the address Adzuna is asked at."""
    with pytest.raises(SourceUnavailableError) as raised:
        AdzunaSearch(web, BERLIN, KEY, api=source_pages({})).fetch()
    assert "app-key" not in str(raised.value) and "app-id" not in str(raised.value)
