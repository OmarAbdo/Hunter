"""Every search source Hunter can read, and each one's web address. The campaigns name what to
search for; a search two campaigns share is read once."""

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from hunter.adapters.sources.searches import adzuna, bundesagentur, eures, jooble
from hunter.adapters.web_client import WebClient
from hunter.application.ports import JobSource
from hunter.domain.discovery.campaign import Campaign, Search
from hunter.domain.pacing import PaceRule

SEARCHES: dict[str, Callable[..., JobSource]] = {
    "bundesagentur": bundesagentur.BundesagenturSearch,
    "eures": eures.EuresSearch,
}
# Sources that need a key: `[keys.<source>]` in var/accounts.toml.
KEYED: dict[str, Callable[..., JobSource]] = {
    "adzuna": adzuna.AdzunaSearch,
    "jooble": jooble.JoobleSearch,
}
APIS: dict[str, str] = {
    "adzuna": adzuna.API,
    "bundesagentur": bundesagentur.API,
    "eures": eures.API,
    "jooble": jooble.API,
}
PACES: dict[str, PaceRule] = {adzuna.HOST: adzuna.PACE}


def searches_of(
    web: WebClient,
    campaigns: Iterable[Campaign],
    apis: Mapping[str, str],
    keys: Mapping[str, dict[str, Any]],
) -> list[JobSource]:
    """One source per search the campaigns name. Raises LookupError for a search source Hunter
    doesn't know, so a misspelt one isn't skipped without a word, and for a keyed one without its
    key."""
    addresses = {**APIS, **apis}
    searches = dict.fromkeys(search for campaign in campaigns for search in campaign.searches)
    unknown = sorted({search.source for search in searches} - set(SEARCHES) - set(KEYED))
    if unknown:
        raise LookupError(f"no search source {', '.join(unknown)}")
    return [source_of(web, search, addresses[search.source], keys) for search in searches]


def source_of(
    web: WebClient, search: Search, address: str, keys: Mapping[str, dict[str, Any]]
) -> JobSource:
    if search.source not in KEYED:
        return SEARCHES[search.source](web, search, api=address)
    if not keys.get(search.source):
        raise LookupError(f"no key for {search.source} in var/accounts.toml")
    return KEYED[search.source](web, search, keys[search.source], api=address)
