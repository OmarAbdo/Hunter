"""One company's coveto board (docs/sources.md): the RSS feed at `<board>.coveto.de/public/rss/`,
where the board is the instance's subdomain (`k11145`). Each job names its place in a line of its
description ("Arbeitsort: Mainz."); its page is usually on the company's own domain."""

import re
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

from hunter.adapters.sources.reading import place_at, read_text
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

API = "https://{board}.coveto.de"
PLACE = re.compile(r"Arbeitsort:\s*([^.]+)\.")
JOB_ID = re.compile(r"(\d+)\.html$")


class CovetoFeed:
    def __init__(self, web: WebClient, board: str, company: str, api: str = API) -> None:
        self.web = web
        self.board = board
        self.company = company
        self.api = api.format(board=board)

    @property
    def name(self) -> str:
        return f"coveto:{self.board}"

    def fetch(self) -> list[Posting]:
        text = read_text(self.web, f"{self.api}/public/rss/")
        try:
            channel = ElementTree.fromstring(text).find("channel")
        except ElementTree.ParseError as error:
            raise SourceUnavailableError(f"{self.name}: not RSS ({error})") from error
        if channel is None:
            raise SourceUnavailableError(f"{self.name}: an RSS feed without a channel")
        return [self._posting(item) for item in channel.findall("item")]

    def _posting(self, item: ElementTree.Element) -> Posting:
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link).strip()
        found = JOB_ID.search(guid)
        job_id = found.group(1) if found else guid
        place = PLACE.search(item.findtext("description") or "")
        published = item.findtext("pubDate")
        return Posting(
            title=(item.findtext("title") or "").strip(),
            company=self.company,
            location=place_at(place.group(1) if place else "", None),
            source=SourceRef(source="coveto", native_id=job_id),
            employer=EmployerRef(ats="coveto", board=self.board, job_id=job_id),
            url=link,
            apply_url=link,
            posted_at=parsedate_to_datetime(published) if published else None,
        )
