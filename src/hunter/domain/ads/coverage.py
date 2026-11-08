"""How much of each taken job's ad Hunter has: the whole ad, a search's few lines, or nothing; or
that the job is gone, its source having taken it down.

Whether a text is the whole ad is a fact about its source, not its length: an employer's feed gives
the ad as written, however short, while these searches only ever show a few lines of it."""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from hunter.domain.discovery.posting import Posting

SNIPPET_SOURCES = frozenset({"adzuna", "careerjet", "indeed-alert", "jooble", "usajobs"})


class AdState(Enum):
    WHOLE = "whole"
    SNIPPET = "snippet"
    NONE = "none"
    GONE = "gone"


def ad_state(posting: Posting, *, gone: bool = False, read: bool = False) -> AdState:
    """`read`: the text was read from the job's own page or details, so it's the whole ad even
    from a source whose search shows only a few lines."""
    if gone:
        return AdState.GONE
    if not posting.description.strip():
        return AdState.NONE
    if posting.source.source in SNIPPET_SOURCES and not read:
        return AdState.SNIPPET
    return AdState.WHOLE


@dataclass(frozen=True)
class TakenJob:
    """A job a campaign took, with what reading its ad found: gone, or the whole ad read."""

    posting: Posting
    gone: bool = False
    read: bool = False

    @property
    def state(self) -> AdState:
        return ad_state(self.posting, gone=self.gone, read=self.read)


FULLNESS = (AdState.NONE, AdState.SNIPPET, AdState.WHOLE)


def fuller(posting: Posting, than: Posting) -> bool:
    """The posting has more of the ad: a snippet over nothing, the whole ad over a snippet."""
    return FULLNESS.index(ad_state(posting)) > FULLNESS.index(ad_state(than))


def coverage(jobs: Iterable[TakenJob]) -> dict[str, Counter[AdState]]:
    """Each source's jobs, counted by how much of their ad Hunter has."""
    counts: dict[str, Counter[AdState]] = {}
    for job in jobs:
        counts.setdefault(job.posting.source.source, Counter()).update((job.state,))
    return counts


def open_jobs(states: Counter[AdState]) -> int:
    """The jobs counted that aren't gone: those Hunter could still apply to."""
    return states.total() - states[AdState.GONE]
