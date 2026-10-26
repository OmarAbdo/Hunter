"""Adzuna's job search API (docs/sources.md), a keyed aggregator over many job boards. A search
needs a country, which picks Adzuna's site for it (`/de/`, `/gb/`, `/us/`), and looks for jobs
published in the last 30 days, 50 a page. Jobs link to Adzuna's own page for them; the
description is a snippet. The key is Omar's (`[keys.adzuna]` in var/accounts.toml): its free plan
allows few requests a day, so a search reads at most 4 pages."""

from datetime import timedelta
from typing import Any

from hunter.adapters.sources.reading import employment_from, parsed_time, place_at, read_json
from hunter.adapters.sources.searches.keyed import keeping_keys_out, without_tracking
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.campaign import Search
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import Posting, SourceRef
from hunter.domain.pacing import PaceRule

API = "https://api.adzuna.com/v1/api/jobs"
HOST = "api.adzuna.com"
# Adzuna's free plan: about 25 requests a minute and 250 a day (Omar's account page shows his).
PACE = PaceRule(min_gap=timedelta(seconds=3), per_day=250)
PAGE_SIZE = 50
MOST_PAGES = 4
DAYS = "30"


class AdzunaSearch:
    def __init__(self, web: WebClient, search: Search, key: dict[str, Any], api: str = API) -> None:
        self.web = web
        self.search = search
        self.key = key
        self.api = api

    @property
    def name(self) -> str:
        place = f"@{self.search.place}" if self.search.place else ""
        country = f",{self.search.country}" if self.search.country else ""
        return f"adzuna:{self.search.query}{place}{country}"

    def fetch(self) -> list[Posting]:
        if not self.search.country:
            raise SourceUnavailableError(f"{self.name}: Adzuna needs a country for each search")
        postings: list[Posting] = []
        for page in range(1, MOST_PAGES + 1):
            jobs = self._jobs(page)
            postings.extend(self._posting(job) for job in jobs)
            if len(jobs) < PAGE_SIZE:
                break
        return postings

    def _jobs(self, page: int) -> list[dict[str, Any]]:
        country = self.search.country.lower()
        params = {
            "app_id": self.key["app_id"],
            "app_key": self.key["app_key"],
            "results_per_page": str(PAGE_SIZE),
            "what": self.search.query,
            **({"where": self.search.place} if self.search.place else {}),
            "max_days_old": DAYS,
            "content-type": "application/json",
        }
        url = f"{self.api}/{country}/search/{page}"
        answer = keeping_keys_out(lambda: read_json(self.web, url, params), self.key.values())
        jobs: list[dict[str, Any]] = answer.get("results") or [] if isinstance(answer, dict) else []
        return jobs

    def _posting(self, job: dict[str, Any]) -> Posting:
        page = without_tracking(job.get("redirect_url") or "")
        return Posting(
            title=job.get("title", "").strip(),
            company=(job.get("company") or {}).get("display_name", "").strip(),
            location=self._place((job.get("location") or {}).get("area") or []),
            source=SourceRef(source="adzuna", native_id=str(job["id"])),
            employment=employment_from(job.get("contract_time")),
            url=page,
            apply_url=page,
            description=job.get("description", ""),
            posted_at=parsed_time(job.get("created")),
        )

    def _place(self, areas: list[str]) -> Location:
        """The first area below the country that names a town. Areas run from the country down
        (Deutschland, Bayern, München, Schwabing), and the parts of a town are towns in GeoNames
        too: Berlin's Mitte would otherwise stand in for Berlin."""
        for area in areas[1:]:
            place = place_at(f"{area}, {self.search.country}", None)
            if place.city:
                return place
        return Location(country=self.search.country or None)
