"""Hunter's pace on other people's sites: a minimum gap between requests to one host, where a site
needs it a daily cap, and any pause a site asked for. Days are counted in UTC.

Time comes from two clocks. Gaps are measured on a steady one that only moves forward, so a
corrected wall clock can't stretch or shorten them; the day and a site's pause, which name times
of day, are read on the wall clock."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta


# Sites that give each company an address of its own but limit across them all (Personio, seen
# 2026-10-27), by how their addresses end. Every other host is a site by itself.
SHARED_SITES = ((".jobs.personio.de", "jobs.personio"), (".jobs.personio.com", "jobs.personio"))


class CapReachedError(Exception):
    pass


def site_of(host: str) -> str:
    """What a host's requests are counted under."""
    return next((site for ending, site in SHARED_SITES if host.endswith(ending)), host)


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
    def __init__(
        self,
        rules: Mapping[str, PaceRule],
        default: PaceRule,
        held: Mapping[str, datetime] | None = None,
        keep: Callable[[str, datetime], None] | None = None,
    ) -> None:
        """`held` are the pauses sites asked for that haven't ended yet, kept from earlier runs;
        `keep` is told each new pause, so later runs can be held by it too."""
        self.rules = dict(rules)
        self.default = default
        self.used: dict[str, HostUse] = {}
        self.held: dict[str, datetime] = dict(held or {})
        self.keep = keep

    def hold(self, host: str, until: datetime) -> None:
        """No request to `host`'s site before `until`: the site asked for the pause."""
        site = site_of(host)
        self.held[site] = max(until, self.held.get(site, until))
        if self.keep:
            self.keep(site, until)

    def wait(self, host: str, now: Moment) -> timedelta:
        """How long to wait before the next request to `host`; refuses once today's cap is used."""
        site = site_of(host)
        held = max(timedelta(0), self.held.get(site, now.wall) - now.wall)
        use = self.used.get(site)
        if use is None:
            return held
        rule = self.rules.get(site, self.default)
        used_today = use.count if use.day == now.wall.date() else 0
        if rule.per_day is not None and used_today >= rule.per_day:
            raise CapReachedError(f"{site}: {rule.per_day} a day reached")
        return max(held, rule.min_gap - timedelta(seconds=now.steady - use.last))

    def record(self, host: str, now: Moment) -> None:
        site = site_of(host)
        use = self.used.get(site)
        today = now.wall.date()
        count = use.count + 1 if use and use.day == today else 1
        self.used[site] = HostUse(last=now.steady, day=today, count=count)
