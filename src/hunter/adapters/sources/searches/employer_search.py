"""The employer's own ad for a job only job boards showed, where the board's own page can't be read:
Careerjet's links are billed clicks, and Indeed asks for a sign-in or a captcha. (LinkedIn's jobs
are read from its public guest pages instead: alerts/linkedin_ads.py.) A web search for the
company and the title, through Edge, names the candidates; the first few that aren't job boards
are read, and the first whose schema.org `JobPosting` names the job's title and company is its ad
(domain/ads/employer_ad.py).

Searches are shared with probing and spread over the engines (edge_search.py). An answer without a
fitting ad is followed by another search at once, on the next engine, whose results differ; after
three answers in a week the job waits. A search that can't be made, with every engine resting say,
leaves the job for a later run."""

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

SEARCHED_FOR = ("careerjet", "indeed-alert")
CANDIDATES = 8  # result pages read for one answer, at most
ANSWERS = 3  # answered searches for one job in a week, each on another engine
LATELY = timedelta(days=7)
Page = Callable[[str], str]
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
    "bebee.",
    "jobleads.",
    "fuchsjobs.",
    "arbeitnow.",
    "jobrobot.",
    "devjobs.",
    "jobs.golem.",
    "jobs.heise.",
    "remotely.",
    "qarera.",
    "rejobs.",
    "meinestadt.",
    "kimeta.",
    "jobted.",
    "builtin.",
    "get-in-it.",
    "jobsora.",
    "jooble.",
    "careerbuilder.",
)


class EmployerAds:
    def __init__(
        self,
        search: WebSearch,
        page: Callable[[str], str],
        answers_lately: Callable[[str], int],
    ) -> None:
        """`answers_lately`: how many searches for a query got an answer in the last week."""
        self.search = search
        self.page = page
        self.answers_lately = answers_lately

    def read(self, posting: Posting) -> str:
        """Searches again at once when an answer holds no fitting ad: the engines take turns, so
        the next answer is another engine's, with other results."""
        if not posting.company.strip():
            raise SourceUnavailableError("a job without a company: its ad can't be told apart")
        query = search_query(posting)
        tries = ANSWERS - self.answers_lately(query)
        if tries <= 0:
            raise SourceUnavailableError(f"{query}: searched {ANSWERS} times lately, no ad found")
        read: set[str] = set()
        for _ in range(tries):
            found = self._first_fit(self.search.links(query), posting, read)
            if found:
                return found
        raise SourceUnavailableError(f"{query}: no ad of the employer's found")

    def _first_fit(self, links: list[str], posting: Posting, read: set[str]) -> str:
        """The first fitting ad among an answer's first results not read before; `read` grows."""
        fresh = [link for link in links if link not in read and not job_board(link)]
        for link in fresh[:CANDIDATES]:
            read.add(link)
            found = self._ad_at(link, posting)
            if found:
                return found
        return ""

    def _ad_at(self, link: str, posting: Posting) -> str:
        try:
            data = posting_data(self.page(link))
        except SourceUnavailableError:
            return ""
        organization = data.get("hiringOrganization") or ""  # an object, or at times just a name
        company = organization.get("name") or "" if isinstance(organization, dict) else organization
        if not fits(posting, str(data.get("title") or ""), str(company)):
            return ""
        return plain_text(data.get("description"))


def job_board(link: str) -> bool:
    host = urlsplit(link).netloc.lower()
    return any(board in host for board in JOB_BOARDS)


def plain_first(plain: Page, browser: Page) -> Page:
    """Reads a page over plain HTTP, in a fraction of a second, and through the browser only when
    the site refuses that; a page that's gone is gone either way."""

    def page(url: str) -> str:
        try:
            return plain(url)
        except SourceUnavailableError as error:
            if error.gone:
                raise
            return browser(url)

    return page


def employer_readers(edge: Edge, database: sqlite3.Connection, plain: Page) -> dict[str, AdReader]:
    """One reader for every source whose own pages can't be read, searching through `edge` at
    the pace the search log keeps, and reading the results with `plain` first."""
    log = SearchLog(database)
    week_ago = datetime.now(UTC) - LATELY
    reader = EmployerAds(
        EdgeSearch(edge.dom, log),
        plain_first(plain, edge.dom),
        lambda query: log.answers(query, week_ago),
    )
    return dict.fromkeys(SEARCHED_FOR, reader)
