"""Which search engines take the next web search, and in which order. Each search goes to the engine
used longest ago, so the searches are spread over every engine before any grows suspicious. An
engine at its share of the last hour waits, and one whose latest searches met a captcha or an answer
it couldn't read rests: for `rest` after one, twice as long after each more in a row, never longer
than `longest_rest`."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import takewhile

HOUR = timedelta(hours=1)
# Answers an engine rests after: a captcha, or a page with neither results nor a known challenge,
# most often a challenge in disguise.
RESTING = frozenset({"captcha", "failed"})


@dataclass(frozen=True)
class Turns:
    per_hour: int = 12  # an engine's searches in any hour: one every five minutes
    rest: timedelta = HOUR
    longest_rest: timedelta = timedelta(hours=24)


@dataclass(frozen=True)
class EngineUse:
    """An engine's recent searches, the oldest first: when, and how each went ("links",
    "nothing", "captcha" or "failed")."""

    name: str
    searches: tuple[tuple[datetime, str], ...] = ()


def resting_until(use: EngineUse, turns: Turns) -> datetime | None:
    """When the engine's rest after its latest captchas or unreadable answers in a row ends; None
    without one."""
    in_a_row = len(list(takewhile(lambda search: search[1] in RESTING, reversed(use.searches))))
    if not in_a_row:
        return None
    rest = min(turns.rest * (1 << (in_a_row - 1)), turns.longest_rest)  # doubled each time
    return use.searches[-1][0] + rest


def free(use: EngineUse, now: datetime, turns: Turns) -> bool:
    rested = resting_until(use, turns)
    lately = sum(1 for when, _ in use.searches if when > now - HOUR)
    return (rested is None or rested <= now) and lately < turns.per_hour


def last_used(use: EngineUse) -> datetime | None:
    return use.searches[-1][0] if use.searches else None


def next_engines(uses: Sequence[EngineUse], now: datetime, turns: Turns) -> list[str]:
    """The engines free to search now, the one used longest ago first; never used, first of all,
    in the order given."""
    ready = [use for use in uses if free(use, now, turns)]
    ready.sort(key=lambda use: (last_used(use) is not None, last_used(use) or now))
    return [use.name for use in ready]
