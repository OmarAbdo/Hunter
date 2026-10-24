"""Where a job is: its country and city, how it's worked, and for a remote job who may take it."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

WORLDWIDE = "WORLDWIDE"

EUROPEAN_UNION = frozenset(
    {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE"}
    | {"IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"}
)
EEA = EUROPEAN_UNION | {"IS", "LI", "NO"}
REGIONS = {
    "EU": EUROPEAN_UNION,
    "EEA": EEA,
    "EUROPE": EEA | {"CH", "GB", "AL", "BA", "ME", "MK", "RS", "MD", "UA"},
    "DACH": frozenset({"DE", "AT", "CH"}),
    "GCC": frozenset({"AE", "SA", "QA", "KW", "BH", "OM"}),
    "NORTH_AMERICA": frozenset({"US", "CA"}),
}
COUNTRY_CODE = re.compile(r"[A-Z]{2}")


class Workplace(Enum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"


def expand_scope(codes: Iterable[str]) -> frozenset[str]:
    """Countries (ISO 3166-1 alpha-2) for a mix of country and region codes; WORLDWIDE stays."""
    return frozenset().union(*(REGIONS.get(code, {code}) for code in codes))


@dataclass(frozen=True)
class Location:
    """`remote_scope` holds the countries or regions a remote job is open to; empty when unknown."""

    country: str | None = None
    city: str | None = None
    workplace: Workplace | None = None
    remote_scope: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.country is not None and not COUNTRY_CODE.fullmatch(self.country):
            raise ValueError(f"Not an ISO 3166 country code: {self.country!r}")

    def reachable_from(self, country: str) -> bool:
        """Whether someone living in `country` can take the job. A remote job without a known
        scope is open to its own country only; a job with no known place, to nobody."""
        if self.workplace is Workplace.REMOTE and self.remote_scope:
            scope = expand_scope(self.remote_scope)
            return WORLDWIDE in scope or country in scope
        return self.country == country
