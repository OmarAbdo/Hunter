"""A campaign is one kind of job search. Plain rules decide which jobs in the pool are its own, and
every job it turns down gets a reason that can be counted."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from hunter.domain.discovery.identity import text_key
from hunter.domain.discovery.language import language_of
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import Employment, Posting


class Rejection(Enum):
    ROLE = "role"
    EXCLUDED_ROLE = "excluded-role"
    WORKPLACE = "workplace"
    PLACE = "place"
    EMPLOYMENT = "employment"
    TOO_OLD = "too-old"
    LANGUAGE = "language"


def mentions_any(title: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, title, re.IGNORECASE) for pattern in patterns)


@dataclass(frozen=True)
class Search:
    """One search the campaign runs on a search source: `query` in `place` ("Softwareentwickler"
    in "Berlin"), and in `country` (ISO 3166) for sources that cover several countries. The source
    decides what an empty place or country means, usually anywhere it covers."""

    source: str
    query: str
    place: str = ""
    country: str = ""


@dataclass(frozen=True)
class Campaign:
    """
    - `home`: the country the candidate works from, which decides the remote jobs it takes.
    - `countries` and `cities`: where onsite and hybrid jobs must be; no cities means anywhere in
      those countries.
    - `roles` and `excluded_roles`: title patterns; no roles means any title.
    - `employment`: the employment types it takes; none means any.
    - `searches`: what it looks for on search sources (the Bundesagentur, EURES); company feeds
      need none, they're read for every campaign.
    - `max_age_days`: how long ago a job may have been posted; none means any age.
    - `languages`: the languages (ISO 639-1) a job ad may be written in; none means any. An ad
      whose language can't be told is taken.
    A job with an unknown workplace counts as onsite; an unknown employment type is taken, and so
    is a job of unknown age. A job open in several places is taken when one of them fits.
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
    searches: tuple[Search, ...] = ()
    max_age_days: int | None = None
    languages: frozenset[str] = frozenset()

    def rejects(self, posting: Posting, now: datetime | None = None) -> Rejection | None:
        """Why the campaign turns the job down, or None when the job is the campaign's own. A
        job's age is judged only when `now` is given."""
        return (
            self._role_rejection(posting.title)
            or self._places_rejection(posting.locations)
            or self._employment_rejection(posting.employment)
            or self._age_rejection(posting.posted_at, now)
            or self._language_rejection(posting)
        )

    def _language_rejection(self, posting: Posting) -> Rejection | None:
        if not self.languages:
            return None
        language = language_of(f"{posting.title}. {posting.description}")
        return Rejection.LANGUAGE if language and language not in self.languages else None

    def _age_rejection(self, posted_at: datetime | None, now: datetime | None) -> Rejection | None:
        if self.max_age_days is None or posted_at is None or now is None:
            return None
        too_old = now - posted_at > timedelta(days=self.max_age_days)
        return Rejection.TOO_OLD if too_old else None

    def _places_rejection(self, locations: tuple[Location, ...]) -> Rejection | None:
        """One place that fits is enough; when none fits, the main place's reason counts."""
        rejections = [self._place_rejection(location) for location in locations]
        return None if None in rejections else rejections[0]

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
