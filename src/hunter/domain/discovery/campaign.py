"""A campaign is one kind of job search. Plain rules decide which jobs in the pool are its own, and
every job it turns down gets a reason that can be counted."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from hunter.domain.discovery.identity import text_key
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import Employment, Posting


class Rejection(Enum):
    ROLE = "role"
    EXCLUDED_ROLE = "excluded-role"
    WORKPLACE = "workplace"
    PLACE = "place"
    EMPLOYMENT = "employment"


def mentions_any(title: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, title, re.IGNORECASE) for pattern in patterns)


@dataclass(frozen=True)
class Campaign:
    """
    - `home`: the country the candidate works from, which decides the remote jobs it takes.
    - `countries` and `cities`: where onsite and hybrid jobs must be; no cities means anywhere in
      those countries.
    - `roles` and `excluded_roles`: title patterns; no roles means any title.
    - `employment`: the employment types it takes; none means any.
    A job with an unknown workplace counts as onsite; an unknown employment type is taken.
    """

    id: str
    title: str
    home: str
    countries: frozenset[str]
    cities: frozenset[str] = frozenset()
    workplaces: frozenset[Workplace] = frozenset(Workplace)
    employment: frozenset[Employment] = frozenset()
    roles: tuple[str, ...] = ()
    excluded_roles: tuple[str, ...] = ()

    def rejects(self, posting: Posting) -> Rejection | None:
        """Why the campaign turns the job down, or None when the job is the campaign's own."""
        return (
            self._role_rejection(posting.title)
            or self._place_rejection(posting.location)
            or self._employment_rejection(posting.employment)
        )

    def _role_rejection(self, title: str) -> Rejection | None:
        if self.roles and not mentions_any(title, self.roles):
            return Rejection.ROLE
        if mentions_any(title, self.excluded_roles):
            return Rejection.EXCLUDED_ROLE
        return None

    def _place_rejection(self, location: Location) -> Rejection | None:
        workplace = location.workplace or Workplace.ONSITE
        if workplace not in self.workplaces:
            return Rejection.WORKPLACE
        if workplace is Workplace.REMOTE:
            return None if location.reachable_from(self.home) else Rejection.PLACE
        in_city = not self.cities or text_key(location.city or "") in self._city_keys()
        return None if location.country in self.countries and in_city else Rejection.PLACE

    def _employment_rejection(self, employment: Employment | None) -> Rejection | None:
        if employment is None or not self.employment or employment in self.employment:
            return None
        return Rejection.EMPLOYMENT

    def _city_keys(self) -> frozenset[str]:
        return frozenset(text_key(city) for city in self.cities)
