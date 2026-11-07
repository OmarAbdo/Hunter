"""How much of each taken job's ad Hunter has: the whole ad, a search's few lines, or nothing; or
that the job is gone, its source having taken it down.

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
    GONE = "gone"


def ad_state(posting: Posting, *, gone: bool = False) -> AdState:
    if gone:
        return AdState.GONE
    if not posting.description.strip():
        return AdState.NONE
    if posting.source.source in SNIPPET_SOURCES:
        return AdState.SNIPPET
    return AdState.WHOLE


FULLNESS = (AdState.NONE, AdState.SNIPPET, AdState.WHOLE)


def fuller(posting: Posting, than: Posting) -> bool:
    """The posting has more of the ad: a snippet over nothing, the whole ad over a snippet."""
    return FULLNESS.index(ad_state(posting)) > FULLNESS.index(ad_state(than))


def coverage(jobs: Iterable[tuple[Posting, bool]]) -> dict[str, Counter[AdState]]:
    """Each source's jobs, each with whether it's gone, counted by how much of their ad Hunter
    has."""
    counts: dict[str, Counter[AdState]] = {}
    for posting, gone in jobs:
        counts.setdefault(posting.source.source, Counter()).update((ad_state(posting, gone=gone),))
    return counts


def open_jobs(states: Counter[AdState]) -> int:
    """The jobs counted that aren't gone: those Hunter could still apply to."""
    return states.total() - states[AdState.GONE]
