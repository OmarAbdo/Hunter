"""How much of each taken job's ad Hunter has: the whole ad, a search's few lines, or nothing.

Whether a text is the whole ad is a fact about its source, not its length: an employer's feed gives
the ad as written, however short, while these searches only ever show a few lines of it."""

from collections import Counter
from collections.abc import Iterable
from enum import Enum

from hunter.domain.discovery.posting import Posting

SNIPPET_SOURCES = frozenset({"adzuna", "careerjet", "indeed-alert", "jooble", "usajobs"})


class AdState(Enum):
    WHOLE = "whole"
    SNIPPET = "snippet"
    NONE = "none"


def ad_state(posting: Posting) -> AdState:
    if not posting.description.strip():
        return AdState.NONE
    if posting.source.source in SNIPPET_SOURCES:
        return AdState.SNIPPET
    return AdState.WHOLE


FULLNESS = (AdState.NONE, AdState.SNIPPET, AdState.WHOLE)


def fuller(posting: Posting, than: Posting) -> bool:
    """The posting has more of the ad: a snippet over nothing, the whole ad over a snippet."""
    return FULLNESS.index(ad_state(posting)) > FULLNESS.index(ad_state(than))


def coverage(postings: Iterable[Posting]) -> dict[str, Counter[AdState]]:
    """Each source's jobs, counted by how much of their ad Hunter has."""
    counts: dict[str, Counter[AdState]] = {}
    for posting in postings:
        counts.setdefault(posting.source.source, Counter())[ad_state(posting)] += 1
    return counts
