"""The employer's own ad for a job only job boards showed, where the board's own page can't be read:
Careerjet's links are billed clicks, Indeed asks for a sign-in or a captcha, and LinkedIn is never
opened. A web search for the company and the title, through Edge, names the candidates; the first
few that aren't job boards are read, and the first whose schema.org `JobPosting` names the job's
title and company is its ad (domain/ads/employer_ad.py).

Searches are few (edge_search.py: 50 an engine a day, shared with probing), so a query answered
in the last week isn't searched again, and a search that can't be made, at the
day's cap say, leaves the job for a later run without a page read."""

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from hunter.adapters.edge_search import Edge, EdgeSearch
from hunter.adapters.html_text import plain_text
from hunter.adapters.sources.reading import posting_data
from hunter.adapters.storage.search_log import SearchLog
from hunter.application.ports import AdReader, SourceUnavailableError, WebSearch
from hunter.domain.ads.employer_ad import fits, search_query
from hunter.domain.discovery.posting import Posting

SEARCHED_FOR = ("careerjet", "indeed-alert", "linkedin-alert")
CANDIDATES = 3  # result pages read for one job, at most
LATELY = timedelta(days=7)  # a query searched since isn't searched again
# Job boards and aggregators: their copies are what Hunter has already, or can't be read.
JOB_BOARDS = (
    "linkedin.",
    "indeed.",
    "careerjet.",
    "stepstone.",
    "xing.",
    "glassdoor.",
    "kununu.",
    "adzuna.",
    "jooble.",
    "monster.",
    "arbeitsagentur.",
    "stellenanzeigen.",
    "jobware.",
    "jobvector.",
    "jobteaser.",
    "talent.com",
    "simplyhired.",
    "ziprecruiter.",
)


class EmployerAds:
    def __init__(
        self,
        search: WebSearch,
        page: Callable[[str], str],
        searched_lately: Callable[[str], bool],
    ) -> None:
        self.search = search
        self.page = page
        self.searched_lately = searched_lately

    def read(self, posting: Posting) -> str:
        query = search_query(posting)
        if self.searched_lately(query):
            raise SourceUnavailableError(f"{query}: searched lately, no ad found")
        links = [link for link in self.search.links(query) if not job_board(link)]
        for link in links[:CANDIDATES]:
            found = self._ad_at(link, posting)
            if found:
                return found
        raise SourceUnavailableError(f"{query}: no ad of the employer's found")

    def _ad_at(self, link: str, posting: Posting) -> str:
        try:
            data = posting_data(self.page(link))
        except SourceUnavailableError:
            return ""
        company = (data.get("hiringOrganization") or {}).get("name") or ""
        if not fits(posting, str(data.get("title") or ""), str(company)):
            return ""
        return plain_text(data.get("description"))


def job_board(link: str) -> bool:
    host = urlsplit(link).netloc.lower()
    return any(board in host for board in JOB_BOARDS)


def employer_readers(edge: Edge, database: sqlite3.Connection) -> dict[str, AdReader]:
    """One reader for every source whose own pages can't be read, searching through `edge` at
    the pace the search log keeps."""
    log = SearchLog(database)
    week_ago = datetime.now(UTC) - LATELY
    reader = EmployerAds(
        EdgeSearch(edge.dom, log), edge.dom, lambda query: log.searched(query, week_ago)
    )
    return dict.fromkeys(SEARCHED_FOR, reader)
