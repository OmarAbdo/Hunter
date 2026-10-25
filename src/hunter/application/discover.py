"""Discovery's use case: read each source, add what it brings to the pool, keep the company
registry up to date, and let every campaign judge each job it hasn't judged yet. A source that
can't be read is reported, and the others still run.

What sources bring is taken in one source at a time, in their order. How they're read (one after
another here, several at a time in the command line) is up to the caller of `take_each`."""

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from hunter.application.ports import (
    CompanyStore,
    JobSource,
    JobStore,
    MatchStore,
    SourceUnavailableError,
)
from hunter.domain.discovery.boards import Board, board_from_key, board_from_link
from hunter.domain.discovery.campaign import Campaign
from hunter.domain.discovery.company import Company, FeedStatus
from hunter.domain.discovery.identity import company_key
from hunter.domain.discovery.posting import Posting


@dataclass(frozen=True)
class Stores:
    jobs: JobStore
    companies: CompanyStore
    matches: MatchStore


@dataclass
class SourceReport:
    """What one source brought in one run. `taken` counts the new matches per campaign."""

    source: str
    fetched: int = 0
    new_jobs: int = 0
    taken: dict[str, int] = field(default_factory=dict)
    error: str | None = None


def discover(
    sources: Iterable[JobSource], campaigns: Sequence[Campaign], stores: Stores, now: datetime
) -> list[SourceReport]:
    return list(discover_each(sources, campaigns, stores, now))


def discover_each(
    sources: Iterable[JobSource], campaigns: Sequence[Campaign], stores: Stores, now: datetime
) -> Iterator[SourceReport]:
    """Each source read and taken in, one after another."""
    return take_each(((source, fetched(source)) for source in sources), campaigns, stores, now)


Fetched = list[Posting] | SourceUnavailableError


def fetched(source: JobSource) -> Fetched:
    """What a source brings, or why it couldn't be read."""
    try:
        return list(source.fetch())
    except SourceUnavailableError as error:
        return error


def take_each(
    readings: Iterable[tuple[JobSource, Fetched]],
    campaigns: Sequence[Campaign],
    stores: Stores,
    now: datetime,
) -> Iterator[SourceReport]:
    """Each source's report as soon as what it brought is taken in, so a run can show progress."""
    discovery = Discovery(campaigns, stores)
    for source, postings in readings:
        yield discovery.take(source, postings, now)


def boards_of(posting: Posting) -> list[Board]:
    """The employer's own board, and any board the posting's links point at."""
    employer = posting.employer
    boards = [Board(ats=employer.ats, slug=employer.board)] if employer else []
    links = (link for link in (posting.url, posting.apply_url) if link)
    return boards + [board for link in links if (board := board_from_link(link))]


class Discovery:
    def __init__(self, campaigns: Sequence[Campaign], stores: Stores) -> None:
        self.campaigns = campaigns
        self.stores = stores

    def take(self, source: JobSource, postings: Fetched, now: datetime) -> SourceReport:
        report = SourceReport(source=source.name)
        if isinstance(postings, SourceUnavailableError):
            report.error = str(postings)
            self._record_feed(source.name, FeedStatus.GONE if postings.gone else None)
            return report
        report.fetched = len(postings)
        for posting in postings:
            self._take_in(posting, now, report)
        self._record_feed(source.name, FeedStatus.LIVE if postings else FeedStatus.EMPTY)
        return report

    def _record_feed(self, source_name: str, status: FeedStatus | None) -> None:
        """A company feed's health, so boards that are gone aren't read again. A board that's only
        down for now (no status) keeps the one it had."""
        board = board_from_key(source_name)
        owner = self.stores.companies.owner_of(board) if board and status else None
        if owner and board and status:
            self.stores.companies.save(owner.checked(board, status))

    def _take_in(self, posting: Posting, now: datetime, report: SourceReport) -> None:
        pooled = self.stores.jobs.add(posting, now)
        report.new_jobs += pooled.is_new
        self._register_company(posting)
        for campaign in self.campaigns:
            if self.stores.matches.decided(pooled.job_id, campaign.id):
                continue
            rejection = campaign.rejects(posting)
            self.stores.matches.record(pooled.job_id, campaign.id, rejection, now)
            if rejection is None:
                report.taken[campaign.id] = report.taken.get(campaign.id, 0) + 1

    def _register_company(self, posting: Posting) -> None:
        """A board belongs to one company: a posting joins its board's owner, whatever name the
        posting gives ("1KOMMA5° Heat GmbH" on 1KOMMA5°'s board); otherwise the company by name."""
        boards = boards_of(posting)
        owners = (owner for board in boards if (owner := self.stores.companies.owner_of(board)))
        known = next(owners, None) or self.stores.companies.get(company_key(posting.company))
        company = known or Company(name=posting.company)
        for board in boards:
            company = company.with_board(board)
        if posting.company_website:
            company = company.with_website(posting.company_website)
        if company != known:
            self.stores.companies.save(company)
