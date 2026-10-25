"""Every search source Hunter can read, and each one's web address. The campaigns name what to
search for; a search two campaigns share is read once."""

from collections.abc import Callable, Iterable, Mapping

from hunter.adapters.sources.searches import bundesagentur
from hunter.adapters.web_client import WebClient
from hunter.application.ports import JobSource
from hunter.domain.discovery.campaign import Campaign

SEARCHES: dict[str, Callable[..., JobSource]] = {
    "bundesagentur": bundesagentur.BundesagenturSearch,
}
APIS: dict[str, str] = {
    "bundesagentur": bundesagentur.API,
}


def searches_of(
    web: WebClient, campaigns: Iterable[Campaign], apis: Mapping[str, str]
) -> list[JobSource]:
    """One source per search the campaigns name. Raises LookupError for a search source Hunter
    doesn't know, so a misspelt one isn't skipped without a word."""
    addresses = {**APIS, **apis}
    searches = dict.fromkeys(search for campaign in campaigns for search in campaign.searches)
    unknown = sorted({search.source for search in searches} - set(SEARCHES))
    if unknown:
        raise LookupError(f"no search source {', '.join(unknown)}")
    return [
        SEARCHES[search.source](web, search, api=addresses[search.source]) for search in searches
    ]
