from dataclasses import replace

import pytest

from hunter.adapters.sources.searches.search_table import searches_of
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.campaign import Campaign, Search

SOFTWARE = Search(source="bundesagentur", query="Softwareentwickler", place="Berlin")
BERLIN = Campaign(id="berlin", title="Berlin", home="DE", countries=frozenset({"DE"}))


def test_every_search_of_the_campaigns_becomes_a_source(web: WebClient) -> None:
    data = Search(source="bundesagentur", query="Data Engineer")
    campaigns = [replace(BERLIN, searches=(SOFTWARE, data))]
    names = [source.name for source in searches_of(web, campaigns, {}, {})]
    assert names == ["bundesagentur:Softwareentwickler@Berlin", "bundesagentur:Data Engineer"]


def test_a_search_two_campaigns_share_is_read_once(web: WebClient) -> None:
    other = replace(BERLIN, id="other", searches=(SOFTWARE,))
    assert len(searches_of(web, [replace(BERLIN, searches=(SOFTWARE,)), other], {}, {})) == 1


def test_an_unknown_search_source_is_refused(web: WebClient) -> None:
    typo = replace(BERLIN, searches=(replace(SOFTWARE, source="bundesagentru"),))
    with pytest.raises(LookupError, match="no search source bundesagentru"):
        searches_of(web, [typo], {}, {})


def test_a_keyed_search_without_its_key_is_reported_and_the_run_goes_on(web: WebClient) -> None:
    keyed = replace(BERLIN, searches=(Search(source="adzuna", query="x", country="DE"),))
    [missing] = searches_of(web, [keyed], {}, {})
    assert missing.name == "adzuna:x,DE"
    with pytest.raises(SourceUnavailableError, match="no key for adzuna in var/accounts.toml"):
        missing.fetch()
    [source] = searches_of(web, [keyed], {}, {"adzuna": {"app_id": "id", "app_key": "key"}})
    assert source.name == "adzuna:x,DE"


def test_every_keyed_source_built_is_wired_in(web: WebClient) -> None:
    key = {"api_key": "k", "app_id": "i", "app_key": "k", "referer": "r", "email": "e"}
    for source in ("adzuna", "careerjet", "jooble", "usajobs"):
        keyed = replace(BERLIN, searches=(Search(source=source, query="x", country="US"),))
        [found] = searches_of(web, [keyed], {}, {source: key})
        assert found.name.startswith(f"{source}:x")


def test_un_careers_is_wired_in(web: WebClient) -> None:
    geneva = replace(BERLIN, searches=(Search(source="uncareers", query="intern", place="Geneva"),))
    [found] = searches_of(web, [geneva], {}, {})
    assert found.name == "uncareers:intern@Geneva"
