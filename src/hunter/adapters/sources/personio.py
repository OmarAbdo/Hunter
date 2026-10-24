"""One company's Personio board (docs/sources.md): `<sub>.jobs.personio.<de|com>/xml`. The board
is the subdomain with its domain, like `zvoove.de`. Offices read "DE | München"; an office called
"Remote" makes the job remote in the other offices' countries."""

from dataclasses import replace
from xml.etree import ElementTree

from hunter.adapters.html_text import plain_text
from hunter.adapters.sources.reading import parsed_time, place_at, read_text
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.identity import text_key
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import EmployerRef, Employment, Posting, SourceRef

API = "https://{sub}.jobs.personio.{tld}"
TYPES = {
    "intern": Employment.INTERNSHIP,
    "trainee": Employment.INTERNSHIP,
    "working_student": Employment.PART_TIME,
    "freelance": Employment.CONTRACT,
    "temporary": Employment.TEMPORARY,
}
# "full-or-part-time" says neither, so it stays unknown.
SCHEDULES = {"full-time": Employment.FULL_TIME, "part-time": Employment.PART_TIME}


class PersonioFeed:
    def __init__(self, web: WebClient, board: str, company: str, api: str = API) -> None:
        self.web = web
        self.board = board
        self.company = company
        sub, _, tld = board.rpartition(".")
        self.api = api.format(sub=sub, tld=tld)
        self.pages = API.format(sub=sub, tld=tld)  # the board's own site, where its jobs are

    @property
    def name(self) -> str:
        return f"personio:{self.board}"

    def fetch(self) -> list[Posting]:
        text = read_text(self.web, f"{self.api}/xml", {"language": "en"})
        try:
            positions = ElementTree.fromstring(text).findall("position")
        except ElementTree.ParseError as error:
            raise SourceUnavailableError(f"{self.name}: not XML ({error})") from error
        return [self._posting(position) for position in positions]

    def _posting(self, position: ElementTree.Element) -> Posting:
        job_id = position.findtext("id") or ""
        offices = [office.text or "" for office in position.iter("office")]
        place, *other_places = places_of(offices)
        return Posting(
            title=(position.findtext("name") or "").strip(),
            company=position.findtext("subcompany") or self.company,
            location=place,
            other_locations=tuple(other_places),
            source=SourceRef(source="personio", native_id=job_id),
            employer=EmployerRef(ats="personio", board=self.board, job_id=job_id),
            employment=TYPES.get(position.findtext("employmentType") or "")
            or SCHEDULES.get(position.findtext("schedule") or ""),
            url=f"{self.pages}/job/{job_id}",
            apply_url=f"{self.pages}/job/{job_id}#apply",
            description=description_of(position),
            posted_at=parsed_time(position.findtext("createdAt")),
        )


def places_of(offices: list[str]) -> list[Location]:
    remote = any(text_key(office) == "remote" for office in offices)
    named = [office for office in offices if office.strip() and text_key(office) != "remote"]
    places = [place_at(office, Workplace.REMOTE if remote else None) for office in named or [""]]
    if not remote:
        return places
    scope = frozenset(place.country for place in places if place.country)
    return [replace(place, remote_scope=scope) for place in places]


def description_of(position: ElementTree.Element) -> str:
    sections = position.findall("jobDescriptions/jobDescription")
    parts = (
        f"{section.findtext('name') or ''}\n\n{plain_text(section.findtext('value'))}"
        for section in sections
    )
    return "\n\n".join(part.strip() for part in parts)
