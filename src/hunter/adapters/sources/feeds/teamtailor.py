"""One company's Teamtailor board (docs/sources.md): the RSS feed at
`<board>.teamtailor.com/jobs.rss`, where the board is the company's subdomain. Each job says how
remote it is and where its offices are."""

import re
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

from hunter.adapters.html_text import plain_text
from hunter.adapters.sources.reading import place_at, read_text
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Workplace
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

API = "https://{board}.teamtailor.com"
PLACES = "{https://teamtailor.com/locations}"
WORKPLACES = {
    "none": Workplace.ONSITE,
    "hybrid": Workplace.HYBRID,
    "temporary": Workplace.HYBRID,
    "fully": Workplace.REMOTE,
}
JOB_ID = re.compile(r"/jobs/(\d+)")


class TeamtailorFeed:
    def __init__(self, web: WebClient, board: str, company: str, api: str = API) -> None:
        self.web = web
        self.board = board
        self.company = company
        self.api = api.format(board=board)

    @property
    def name(self) -> str:
        return f"teamtailor:{self.board}"

    def fetch(self) -> list[Posting]:
        text = read_text(self.web, f"{self.api}/jobs.rss")
        try:
            channel = ElementTree.fromstring(text).find("channel")
        except ElementTree.ParseError as error:
            raise SourceUnavailableError(f"{self.name}: not RSS ({error})") from error
        if channel is None:
            raise SourceUnavailableError(f"{self.name}: an RSS feed without a channel")
        company = channel.findtext("title") or self.company
        return [self._posting(item, company) for item in channel.findall("item")]

    def _posting(self, item: ElementTree.Element, company: str) -> Posting:
        link = item.findtext("link") or ""
        found = JOB_ID.search(link)
        job_id = found.group(1) if found else item.findtext("guid") or link
        workplace = WORKPLACES.get(item.findtext("remoteStatus") or "")
        offices = [
            f"{office.findtext(f'{PLACES}city') or office.findtext(f'{PLACES}name') or ''}, "
            f"{office.findtext(f'{PLACES}country') or ''}"
            for office in item.iter(f"{PLACES}location")
        ]
        place, *other_places = [place_at(office, workplace) for office in offices or [""]]
        published = item.findtext("pubDate")
        return Posting(
            title=(item.findtext("title") or "").strip(),
            company=company,
            location=place,
            other_locations=tuple(other_places),
            source=SourceRef(source="teamtailor", native_id=job_id),
            employer=EmployerRef(ats="teamtailor", board=self.board, job_id=job_id),
            url=link,
            apply_url=link,
            description=plain_text(item.findtext("description")),
            posted_at=parsedate_to_datetime(published) if published else None,
        )
