from collections.abc import Callable, Mapping
from datetime import UTC, datetime

import pytest

from hunter.adapters.sources.searches import eures
from hunter.adapters.sources.searches.eures import EuresSearch, search_body
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.campaign import Search
from hunter.domain.discovery.posting import Employment, SourceRef

Pages = Callable[[Mapping[str, str]], str]
BERLIN = Search(source="eures", query="software engineer", place="de3")
SAVED = "eures-software-engineer.json"
SEARCH_PATH = "/jv-search/search"


def fetched(web: WebClient, source_pages: Pages, search: Search = BERLIN) -> list[object]:
    api = source_pages({SEARCH_PATH: SAVED})
    return list(EuresSearch(web, search, api=api).fetch())


def test_a_search_brings_the_jobs_it_finds(web: WebClient, source_pages: Pages) -> None:
    junini, *_ = EuresSearch(web, BERLIN, api=source_pages({SEARCH_PATH: SAVED})).fetch()
    assert junini.title == "Software Engineer (Founding Team) (Softwareentwickler/in)"
    assert (junini.company, junini.company_website) == ("Junini GmbH", "http://www.junini.io")
    assert (junini.location.country, junini.location.city) == ("DE", "Berlin")
    assert junini.employment is Employment.FULL_TIME
    assert junini.posted_at == datetime.fromtimestamp(1790804039.114, UTC)
    assert (
        junini.url == f"https://europa.eu/eures/portal/jv-se/jv-details/{junini.source.native_id}"
    )


def test_a_job_open_in_several_regions_keeps_them_all(web: WebClient, source_pages: Pages) -> None:
    _, capgemini, *_ = EuresSearch(web, BERLIN, api=source_pages({SEARCH_PATH: SAVED})).fetch()
    cities = [location.city for location in capgemini.locations]
    assert len(cities) == 6
    assert (cities[0], cities[3]) == ("Hamburg", "Berlin")


def test_a_bundesagentur_job_says_which_one_it_is(web: WebClient, source_pages: Pages) -> None:
    junini, *_ = EuresSearch(web, BERLIN, api=source_pages({SEARCH_PATH: SAVED})).fetch()
    assert junini.same_as == (SourceRef(source="bundesagentur", native_id="10000-1208091153-S"),)


def test_a_job_from_elsewhere_names_no_other_source(web: WebClient, source_pages: Pages) -> None:
    *_, forto, dutch = EuresSearch(web, BERLIN, api=source_pages({SEARCH_PATH: SAVED})).fetch()
    assert (forto.company, forto.company_website) == ("Forto Logistics SE & Co. KG", None)
    assert dutch.same_as == ()
    assert (dutch.company, dutch.location.country) == ("", "NL")
    assert dutch.employment is Employment.FULL_TIME


def test_a_full_page_means_there_may_be_another_up_to_the_most_pages(
    web: WebClient, source_pages: Pages, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eures, "PAGE_SIZE", 4)
    monkeypatch.setattr(eures, "MOST_PAGES", 2)
    assert len(fetched(web, source_pages)) == 8


def test_the_search_asks_for_titles_in_the_place_from_the_last_month() -> None:
    body = search_body(BERLIN, page=2)
    assert body["keywords"] == [{"keyword": "software engineer", "specificSearchCode": "TITLE"}]
    assert (body["locationCodes"], body["page"], body["publicationPeriod"]) == (
        ["de3"],
        2,
        "LAST_MONTH",
    )
    assert search_body(Search(source="eures", query="x"), page=1)["locationCodes"] == []


def test_a_search_is_named_by_its_query_and_place(web: WebClient) -> None:
    assert EuresSearch(web, BERLIN).name == "eures:software engineer@de3"
    assert EuresSearch(web, Search(source="eures", query="x")).name == "eures:x"


def test_an_answer_that_is_no_job_list_is_reported(web: WebClient, source_pages: Pages) -> None:
    api = source_pages({SEARCH_PATH: "lever-unzer.json"})
    with pytest.raises(SourceUnavailableError, match="isn't a job list"):
        EuresSearch(web, BERLIN, api=api).fetch()
