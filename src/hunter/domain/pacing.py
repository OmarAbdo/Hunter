"""Hunter's pace on other people's sites: a minimum gap between requests to one host, where a site
needs it a daily cap, and any pause a site asked for. Days are counted in UTC.

Time comes from two clocks. Gaps are measured on a steady one that only moves forward, so a
corrected wall clock can't stretch or shorten them; the day and a site's pause, which name times
of day, are read on the wall clock."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta


class CapReachedError(Exception):
    pass


@dataclass(frozen=True)
class PaceRule:
    min_gap: timedelta
    per_day: int | None = None


@dataclass(frozen=True)
class Moment:
    """Now on both clocks: `wall` is the time of day (UTC), `steady` the seconds on a clock that
    only moves forward (`time.monotonic()`)."""

    wall: datetime
    steady: float


@dataclass
class HostUse:
    last: float  # on the steady clock
    day: date
    count: int


class Pacing:
    def __init__(self, rules: Mapping[str, PaceRule], default: PaceRule) -> None:
        self.rules = dict(rules)
        self.default = default
        self.used: dict[str, HostUse] = {}
        self.held: dict[str, datetime] = {}

    def hold(self, host: str, until: datetime) -> None:
        """No request to `host` before `until`: the site asked for the pause."""
        self.held[host] = max(until, self.held.get(host, until))

    def wait(self, host: str, now: Moment) -> timedelta:
        """How long to wait before the next request to `host`; refuses once today's cap is used."""
        held = max(timedelta(0), self.held.get(host, now.wall) - now.wall)
        use = self.used.get(host)
        if use is None:
            return held
        rule = self.rules.get(host, self.default)
        used_today = use.count if use.day == now.wall.date() else 0
        if rule.per_day is not None and used_today >= rule.per_day:
            raise CapReachedError(f"{host}: {rule.per_day} a day reached")
        return max(held, rule.min_gap - timedelta(seconds=now.steady - use.last))

    def record(self, host: str, now: Moment) -> None:
        use = self.used.get(host)
        today = now.wall.date()
        count = use.count + 1 if use and use.day == today else 1
        self.used[host] = HostUse(last=now.steady, day=today, count=count)
