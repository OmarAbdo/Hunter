"""One company's softgarden board (docs/sources.md): the list of vacancies at
`<board>.softgarden.io/de/vacancies`, a web page, read where its robots.txt allows. softgarden
publishes no feed; the page lists every job, each in a row of columns the company chooses: the
title always, mostly also the date, the places, and on a group's board the company."""

from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

from hunter.adapters.sources.reading import place_at, read_page
from hunter.adapters.web_client import WebClient
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

API = "https://{board}.softgarden.io"
JOB_ROW = "job_id_"
TEXT_COLUMNS = frozenset({"title", "date", "sg_company_id"})


class VacancyRows(HTMLParser):
    """The rows of the vacancy list, each a dict of its id, link, columns and places."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, Any]] = []
        self.depth = 0  # how deep inside the current row's <div>s; 0 outside any row
        self.column: tuple[str, int] | None = None  # the column being read, and its depth
        self.in_place = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        found = {name: value or "" for name, value in attrs}
        if tag == "div":
            self._enter_div(found)
        elif tag == "a" and self.column and self.column[0] == "title":
            self.rows[-1]["href"] = found.get("href", "")
        elif tag == "span" and "location-view-item" in found.get("class", ""):
            self.in_place = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "span":
            self.in_place = False
        elif tag == "div" and self.depth:
            if self.column and self.column[1] == self.depth:
                self.column = None
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.depth:
            return
        row = self.rows[-1]
        if self.in_place:
            row["places"].append(data.strip().rstrip(",").strip())
        elif self.column and self.column[0] in TEXT_COLUMNS:
            row[self.column[0]] = (row.get(self.column[0], "") + data).strip()

    def _enter_div(self, found: dict[str, str]) -> None:
        if found.get("id", "").startswith(JOB_ROW):
            self.rows.append({"id": found["id"].removeprefix(JOB_ROW), "places": []})
            self.depth = 1
        elif self.depth:
            self.depth += 1
            classes = found.get("class", "").split()
            if classes[:1] == ["matchValue"] and len(classes) > 1:
                self.column = (classes[1], self.depth)


class SoftgardenFeed:
    def __init__(self, web: WebClient, board: str, company: str, api: str = API) -> None:
        self.web = web
        self.board = board
        self.company = company
        self.api = api.format(board=board)

    @property
    def name(self) -> str:
        return f"softgarden:{self.board}"

    def fetch(self) -> list[Posting]:
        page = f"{self.api}/de/vacancies"
        rows = VacancyRows()
        rows.feed(read_page(self.web, page))
        return [self._posting(row, page) for row in rows.rows if row.get("title")]

    def _posting(self, row: dict[str, Any], page: str) -> Posting:
        place, *other_places = [place_at(town, None) for town in row["places"] or [""]]
        link = urljoin(page, row.get("href", ""))
        return Posting(
            title=row["title"],
            company=row.get("sg_company_id") or self.company,
            location=place,
            other_locations=tuple(other_places),
            source=SourceRef(source="softgarden", native_id=row["id"]),
            employer=EmployerRef(ats="softgarden", board=self.board, job_id=row["id"]),
            url=link,
            apply_url=link,
            posted_at=listed_on(row.get("date", "")),
        )


def listed_on(text: str) -> datetime | None:
    """The list's date, "23.10.26"."""
    try:
        return datetime.strptime(text, "%d.%m.%y").replace(tzinfo=UTC)
    except ValueError:
        return None
