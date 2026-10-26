from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from urllib.parse import urlencode

import pytest

from hunter.adapters.sources.searches import careerjet
from hunter.adapters.sources.searches.careerjet import CareerjetSearch, sent_headers
from hunter.adapters.web_client import USER_AGENT, WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.campaign import Search
from hunter.domain.discovery.posting import Posting

Pages = Callable[[Mapping[str, str]], str]
BERLIN = Search(source="careerjet", query="software engineer", place="Berlin", country="DE")
KEY = {"api_key": "the-key", "referer": "https://example.org/hunter"}
SAVED = "careerjet-de-berlin.json"


def page_path(page: int, size: int = 50, place: str = "Berlin", locale: str = "de_DE") -> str:
    search = {"locale_code": locale, "keywords": "software engineer", "location": place}
    asker = {"user_ip": "127.0.0.1", "user_agent": USER_AGENT}
    return f"/?{urlencode({**search, **asker, 'pagesize': str(size), 'page': str(page)})}"


def postings(source_pages: Pages, web: WebClient) -> list[Posting]:
    return CareerjetSearch(web, BERLIN, KEY, api=source_pages({page_path(1): SAVED}) + "/").fetch()


def test_a_search_brings_the_jobs_it_finds(source_pages: Pages, web: WebClient) -> None:
    hensoldt, vattenfall, alten = postings(source_pages, web)
    assert (hensoldt.title, hensoldt.company) == (
        "Lead Software Engineer / Developer (m/w/d) - Mission Planning",
        "Hensoldt",
    )
    assert hensoldt.url == hensoldt.apply_url == "https://jobviewtrack.com/v2/a-token-for-hensoldt"
    assert hensoldt.posted_at == datetime(2026, 10, 24, 22, 14, 29, tzinfo=UTC)
    assert hensoldt.description.startswith("und Software für die Bereiche Luft")
    assert "<b>" not in alten.description
    assert alten.company == "Alten Consulting Services"


def test_the_same_job_advertised_twice_is_one_posting(source_pages: Pages, web: WebClient) -> None:
    """Careerjet has no job ids, and its links change with every answer: a job is known by its
    company, title and place. The first advertisement read is kept."""
    _, vattenfall, _ = postings(source_pages, web)
    assert vattenfall.source.native_id == vattenfall.fuzzy_key
    assert vattenfall.source.source == "careerjet"
    assert vattenfall.posted_at == datetime(2026, 10, 17, 7, 24, 29, tzinfo=UTC)


def test_a_job_in_several_towns_is_open_in_each(source_pages: Pages, web: WebClient) -> None:
    hensoldt, vattenfall, alten = postings(source_pages, web)
    assert [(place.country, place.city) for place in hensoldt.locations] == [("DE", "Berlin")]
    assert [place.city for place in vattenfall.locations] == ["Hamburg", "Berlin"]
    assert [place.city for place in alten.locations] == ["Munich", "Berlin"]


def test_a_full_page_means_there_may_be_another(
    source_pages: Pages, web: WebClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(careerjet, "PAGE_SIZE", 4)
    api = source_pages({page_path(1, 4): SAVED}) + "/"
    with pytest.raises(SourceUnavailableError, match="HTTP 404"):  # page 2 was asked for
        CareerjetSearch(web, BERLIN, KEY, api=api).fetch()


def test_a_page_with_no_new_job_ends_the_search(
    source_pages: Pages, web: WebClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(careerjet, "PAGE_SIZE", 4)
    api = source_pages({page_path(1, 4): SAVED, page_path(2, 4): SAVED}) + "/"
    assert len(CareerjetSearch(web, BERLIN, KEY, api=api).fetch()) == 3  # page 3 isn't asked for


def test_the_country_picks_careerjet_s_site(source_pages: Pages, web: WebClient) -> None:
    london = Search(source="careerjet", query="software engineer", place="London", country="gb")
    api = source_pages({page_path(1, place="London", locale="en_GB"): SAVED}) + "/"
    assert len(CareerjetSearch(web, london, KEY, api=api).fetch()) == 3


def test_a_search_without_a_country_careerjet_serves_is_refused(web: WebClient) -> None:
    anywhere = Search(source="careerjet", query="software engineer")
    with pytest.raises(SourceUnavailableError, match="needs a country"):
        CareerjetSearch(web, anywhere, KEY).fetch()
    iceland = Search(source="careerjet", query="software engineer", country="IS")
    with pytest.raises(SourceUnavailableError, match="no site for IS"):
        CareerjetSearch(web, iceland, KEY).fetch()


def test_a_place_careerjet_cannot_tell_apart_is_refused(
    source_pages: Pages, web: WebClient
) -> None:
    """For an unknown or ambiguous place Careerjet runs no search and names the places it knows."""
    springfield = Search("careerjet", "software engineer", place="Springfield", country="US")
    path = page_path(1, place="Springfield", locale="en_US")
    api = source_pages({path: "careerjet-springfield.json"}) + "/"
    with pytest.raises(SourceUnavailableError, match="Springfield, IL; Springfield, MA"):
        CareerjetSearch(web, springfield, KEY, api=api).fetch()


def test_the_key_and_referer_are_sent_as_headers() -> None:
    assert sent_headers(KEY) == {
        "Authorization": "Basic dGhlLWtleTo=",  # "the-key:" in Base64
        "Referer": "https://example.org/hunter",
    }


def test_a_search_is_named_by_its_query_place_and_country(web: WebClient) -> None:
    assert CareerjetSearch(web, BERLIN, KEY).name == "careerjet:software engineer@Berlin,DE"
    anywhere = Search(source="careerjet", query="software engineer")
    assert CareerjetSearch(web, anywhere, KEY).name == "careerjet:software engineer"


def test_a_failed_search_never_shows_the_key(source_pages: Pages, web: WebClient) -> None:
    """Errors are printed in a run's report; they must not carry the key or the referer."""
    with pytest.raises(SourceUnavailableError) as raised:
        CareerjetSearch(web, BERLIN, KEY, api=source_pages({}) + "/").fetch()
    assert "the-key" not in str(raised.value) and "example.org" not in str(raised.value)
    assert "dGhlLWtleTo" not in str(raised.value)
