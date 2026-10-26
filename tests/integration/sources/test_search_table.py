from dataclasses import replace

import pytest

from hunter.adapters.sources.searches.search_table import searches_of
from hunter.adapters.web_client import WebClient
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


def test_a_keyed_search_source_needs_its_key(web: WebClient) -> None:
    keyed = replace(BERLIN, searches=(Search(source="adzuna", query="x", country="DE"),))
    with pytest.raises(LookupError, match="no key for adzuna"):
        searches_of(web, [keyed], {}, {})
    [source] = searches_of(web, [keyed], {}, {"adzuna": {"app_id": "id", "app_key": "key"}})
    assert source.name == "adzuna:x,DE"
