"""Every search source Hunter can read, and each one's web address. The campaigns name what to
search for; a search two campaigns share is read once."""

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from hunter.adapters.sources.searches import (
    adzuna,
    bundesagentur,
    careerjet,
    eures,
    jooble,
    usajobs,
)
from hunter.adapters.web_client import WebClient
from hunter.application.ports import JobSource, SourceUnavailableError
from hunter.domain.discovery.campaign import Campaign, Search
from hunter.domain.discovery.posting import Posting
from hunter.domain.pacing import PaceRule

SEARCHES: dict[str, Callable[..., JobSource]] = {
    "bundesagentur": bundesagentur.BundesagenturSearch,
    "eures": eures.EuresSearch,
}
# Sources that need a key: `[keys.<source>]` in var/accounts.toml.
KEYED: dict[str, Callable[..., JobSource]] = {
    "adzuna": adzuna.AdzunaSearch,
    "careerjet": careerjet.CareerjetSearch,
    "jooble": jooble.JoobleSearch,
    "usajobs": usajobs.UsaJobsSearch,
}
APIS: dict[str, str] = {
    "adzuna": adzuna.API,
    "bundesagentur": bundesagentur.API,
    "careerjet": careerjet.API,
    "eures": eures.API,
    "jooble": jooble.API,
    "usajobs": usajobs.API,
}
PACES: dict[str, PaceRule] = {adzuna.HOST: adzuna.PACE}


def searches_of(
    web: WebClient,
    campaigns: Iterable[Campaign],
    apis: Mapping[str, str],
    keys: Mapping[str, dict[str, Any]],
) -> list[JobSource]:
    """One source per search the campaigns name. Raises LookupError for a search source Hunter
    doesn't know, so a misspelt one isn't skipped without a word. A keyed one without its key is
    reported as unavailable instead, and the run goes on."""
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
    found = KEYED[search.source](web, search, keys.get(search.source) or {}, api=address)
    return found if keys.get(search.source) else WithoutKey(found, search.source)


class WithoutKey:
    """A keyed search whose key isn't in var/accounts.toml: every run reports it unavailable."""

    def __init__(self, keyed: JobSource, source: str) -> None:
        self.keyed = keyed
        self.source = source

    @property
    def name(self) -> str:
        return self.keyed.name

    def fetch(self) -> list[Posting]:
        raise SourceUnavailableError(f"{self.name}: no key for {self.source} in var/accounts.toml")
