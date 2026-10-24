"""Hunter's pace on other people's sites: a minimum gap between requests to one host and, where a
site needs it, a daily cap. Days are counted in UTC."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta


class CapReachedError(Exception):
    pass


@dataclass(frozen=True)
class PaceRule:
    min_gap: timedelta
    per_day: int | None = None


@dataclass
class HostUse:
    last: datetime
    day: date
    count: int


class Pacing:
    def __init__(self, rules: Mapping[str, PaceRule], default: PaceRule) -> None:
        self.rules, self.default = dict(rules), default
        self.used: dict[str, HostUse] = {}

    def rule(self, host: str) -> PaceRule:
        return self.rules.get(host, self.default)

    def wait(self, host: str, now: datetime) -> timedelta:
        """How long to wait before the next request to `host`; refuses once today's cap is used."""
        use, rule = self.used.get(host), self.rule(host)
        if use is None:
            return timedelta(0)
        today = use.count if use.day == now.date() else 0
        if rule.per_day is not None and today >= rule.per_day:
            raise CapReachedError(f"{host}: {rule.per_day} a day reached")
        return max(timedelta(0), use.last + rule.min_gap - now)

    def record(self, host: str, now: datetime) -> None:
        use = self.used.get(host)
        count = use.count + 1 if use and use.day == now.date() else 1
        self.used[host] = HostUse(last=now, day=now.date(), count=count)
