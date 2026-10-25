"""One company's onlyfy board (docs/sources.md), the system once called Prescreen: the job list
page at `<board>.onlyfy.jobs`, 10 jobs a page, read where its robots.txt allows. onlyfy publishes
no feed. Each job is a card with its title and a line of facts: the town first, then the
employment type and the date, among others the company chooses."""

import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from hunter.adapters.sources.reading import employment_from, place_at, read_page
from hunter.adapters.web_client import WebClient
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

API = "https://{board}.onlyfy.jobs"
PAGE_SIZE = 10
MOST_PAGES = 30  # 300 jobs
DATE = re.compile(r"\d{2}\.\d{2}\.\d{4}")
FIELDS = frozenset({"job-title", "job-more-info"})


class JobCards(HTMLParser):
    """The cards of the job list, each a dict of its link, title and line of facts."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cards: list[dict[str, str]] = []
        self.field: str | None = None

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        found = {name: value or "" for name, value in attrs}
        testid = found.get("data-testid", "")
        if testid == "job-card":
            self.cards.append({"href": found.get("href", "")})
        elif testid in FIELDS and self.cards:
            self.field = testid

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h3", "div"}:
            self.field = None

    def handle_data(self, data: str) -> None:
        if self.field:
            card = self.cards[-1]
            card[self.field] = (card.get(self.field, "") + data).strip()


class OnlyfyFeed:
    def __init__(self, web: WebClient, board: str, company: str, api: str = API) -> None:
        self.web = web
        self.board = board
        self.company = company
        self.api = api.format(board=board)

    @property
    def name(self) -> str:
        return f"onlyfy:{self.board}"

    def fetch(self) -> list[Posting]:
        """Page after page, until one isn't full or brings no job not already read: a board with
        one page shows that page again for every page number after it."""
        postings: dict[str, Posting] = {}
        for page in range(1, MOST_PAGES + 1):
            cards = JobCards()
            cards.feed(read_page(self.web, f"{self.api}/?page={page}"))
            found = [self._posting(card) for card in cards.cards if card.get("job-title")]
            new = {posting.source.native_id: posting for posting in found}.keys() - postings.keys()
            postings.update({posting.source.native_id: posting for posting in found})
            if not new or len(cards.cards) < PAGE_SIZE:
                break
        return list(postings.values())

    def _posting(self, card: dict[str, str]) -> Posting:
        facts = [fact.strip() for fact in card.get("job-more-info", "").split("|")]
        path = urlsplit(card["href"]).path  # without the query that names the list's page
        link = urljoin(f"{self.api}/", path)
        job_id = path.rstrip("/").rsplit("/", 1)[-1]
        return Posting(
            title=card["job-title"],
            company=self.company,
            location=place_at(facts[0], None),
            source=SourceRef(source="onlyfy", native_id=job_id),
            employer=EmployerRef(ats="onlyfy", board=self.board, job_id=job_id),
            employment=employment_from(facts[1] if len(facts) > 1 else None),
            url=link,
            apply_url=link,
            posted_at=listed_on(facts),
        )


def listed_on(facts: list[str]) -> datetime | None:
    found = next((fact for fact in facts if DATE.fullmatch(fact)), None)
    return datetime.strptime(found, "%d.%m.%Y").replace(tzinfo=UTC) if found else None
