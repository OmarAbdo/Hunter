"""One company's SAP SuccessFactors career site (docs/sources.md), the kind built with its Career
Site Builder on the company's own host (`jobs.bechtle.com`), which is the board. Every such site
serves all of its jobs as RSS at `/sitemal.xml`, a feed SAP doesn't document but every instance
has. Each job gives its place as "town, country, postcode" (or "town, state, state name,
country"), which its title repeats in brackets."""

import html
import re
from xml.etree import ElementTree

from hunter.adapters.html_text import plain_text
from hunter.adapters.sources.reading import place_at, read_text
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

API = "https://{board}"
GOOGLE = "{http://base.google.com/ns/1.0}"
COUNTRY_CODE = re.compile(r"[A-Z]{2}")


class SuccessFactorsFeed:
    def __init__(self, web: WebClient, board: str, company: str, api: str = API) -> None:
        self.web = web
        self.board = board
        self.company = company
        self.api = api.format(board=board)

    @property
    def name(self) -> str:
        return f"successfactors:{self.board}"

    def fetch(self) -> list[Posting]:
        text = read_text(self.web, f"{self.api}/sitemal.xml")
        try:
            channel = ElementTree.fromstring(text).find("channel")
        except ElementTree.ParseError as error:
            raise SourceUnavailableError(f"{self.name}: not RSS ({error})") from error
        if channel is None:
            raise SourceUnavailableError(f"{self.name}: an RSS feed without a channel")
        return [self._posting(item) for item in channel.findall("item")]

    def _posting(self, item: ElementTree.Element) -> Posting:
        where = (item.findtext(f"{GOOGLE}location") or "").strip()
        title = (item.findtext("title") or "").strip().removesuffix(f"({where})").strip()
        job_id = (item.findtext("guid") or "").strip()
        link = (item.findtext("link") or "").strip()
        return Posting(
            title=title,
            company=(item.findtext(f"{GOOGLE}employer") or "").strip() or self.company,
            location=place_of(where),
            source=SourceRef(source="successfactors", native_id=job_id),
            employer=EmployerRef(ats="successfactors", board=self.board, job_id=job_id),
            url=link,
            apply_url=link,
            description=plain_text(html.unescape(item.findtext("description") or "")),
        )


def place_of(where: str) -> Location:
    """The town comes first, and the country is the last part that's a two-letter code: "Budapest,
    HU, 1037", "Morristown, NJ, New Jersey, US"."""
    parts = [part.strip() for part in where.split(",")]
    codes = [part for part in parts[1:] if COUNTRY_CODE.fullmatch(part)]
    return place_at(f"{parts[0]}, {codes[-1]}" if codes else parts[0], None)
