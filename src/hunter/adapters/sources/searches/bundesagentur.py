"""The Bundesagentur für Arbeit's job search (docs/sources.md): the public search behind
arbeitsagentur.de/jobsuche, read a page of 100 jobs at a time. A search for jobs in a place takes
those within 25 km of it; one without a place covers Germany. Only jobs published in the last 30
days are asked for. The list has no descriptions; most jobs link to the board or employer site
they came from."""

from datetime import UTC, date, datetime
from typing import Any

from hunter.adapters.sources.reading import place_at, read_json
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.campaign import Search
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import Employment, Posting, SourceRef

API = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
KEY = {"X-API-Key": "jobboerse-jobsuche"}  # the site's own public key, the same for everyone
JOB_PAGE = "https://www.arbeitsagentur.de/jobsuche/jobdetail/{ref}"
PAGE_SIZE = 100
MOST_PAGES = 20  # 2,000 jobs: more than any one search of a campaign should bring
RADIUS_KM = "25"
DAYS = "30"
FULLY_REMOTE = 100  # the share of home office that makes a job remote
PART_TIME_HOURS = (
    "arbeitszeitTeilzeitVormittag",
    "arbeitszeitTeilzeitNachmittag",
    "arbeitszeitTeilzeitAbend",
    "arbeitszeitTeilzeitFlexibel",
)


class BundesagenturSearch:
    def __init__(self, web: WebClient, search: Search, api: str = API) -> None:
        self.web = web
        self.search = search
        self.api = api

    @property
    def name(self) -> str:
        place = f"@{self.search.place}" if self.search.place else ""
        return f"bundesagentur:{self.search.query}{place}"

    def fetch(self) -> list[Posting]:
        postings: list[Posting] = []
        for page in range(1, MOST_PAGES + 1):
            rows = self._rows(page)
            postings.extend(posting_from(row) for row in rows)
            if len(rows) < PAGE_SIZE:
                break
        return postings

    def _rows(self, page: int) -> list[dict[str, Any]]:
        answer = read_json(self.web, f"{self.api}/pc/v6/jobs", self._params(page), KEY)
        if not isinstance(answer, dict):
            raise SourceUnavailableError(f"{self.name}: an answer that isn't a job list")
        rows: list[dict[str, Any]] = answer.get("ergebnisliste") or []
        return rows

    def _params(self, page: int) -> dict[str, str]:
        place = {"wo": self.search.place, "umkreis": RADIUS_KM} if self.search.place else {}
        return {
            "was": self.search.query,
            **place,
            "angebotsart": "1",  # jobs, not apprenticeships or self-employment
            "veroeffentlichtseit": DAYS,
            "size": str(PAGE_SIZE),
            "page": str(page),
        }


def posting_from(row: dict[str, Any]) -> Posting:
    ref = row["referenznummer"]
    page = JOB_PAGE.format(ref=ref)
    published = row.get("datumErsteVeroeffentlichung")
    return Posting(
        title=row.get("stellenangebotsTitel", "").strip(),
        company=row.get("firma", "").strip(),
        location=location_of(row),
        source=SourceRef(source="bundesagentur", native_id=ref),
        employment=employment_of(row),
        url=page,
        apply_url=row.get("externeURL") or page,
        posted_at=datetime.combine(date.fromisoformat(published), datetime.min.time(), UTC)
        if published
        else None,
    )


def location_of(row: dict[str, Any]) -> Location:
    places = row.get("stellenlokationen") or [{}]
    address = places[0].get("adresse", {})
    country = "Germany" if address.get("land", "DEUTSCHLAND") == "DEUTSCHLAND" else address["land"]
    return place_at(f"{address.get('ort', '')}, {country}", workplace_of(row))


def workplace_of(row: dict[str, Any]) -> Workplace | None:
    """Some home office makes a job hybrid, all of it remote; none said is no way to tell."""
    if row.get("homeofficeprozent") == FULLY_REMOTE:
        return Workplace.REMOTE
    home_office = row.get("homeofficemoeglich")
    if home_office is None:
        return None
    return Workplace.HYBRID if home_office else Workplace.ONSITE


def employment_of(row: dict[str, Any]) -> Employment | None:
    if row.get("arbeitszeitVollzeit"):
        return Employment.FULL_TIME
    return Employment.PART_TIME if any(row.get(hours) for hours in PART_TIME_HOURS) else None
