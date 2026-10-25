"""Probing: finding the board of a company Hunter knows only by name (seen in an Indeed alert, say),
so its jobs can come from the employer's own system from then on. A company is probed once and
logged, found or not; one that couldn't be probed (a site didn't answer) is tried again later."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime

from hunter.application.ports import BoardCheck, CompanyStore, ProbeLog, SourceUnavailableError
from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.company import Company, FeedStatus
from hunter.domain.discovery.probing import board_candidates


@dataclass(frozen=True)
class ProbeStores:
    companies: CompanyStore
    log: ProbeLog


@dataclass(frozen=True)
class ProbeResult:
    company: str
    board: Board | None
    error: str | None = None


def probe(
    companies: Iterable[Company], check: BoardCheck, stores: ProbeStores, now: datetime
) -> Iterator[ProbeResult]:
    """Each company's result as soon as it's probed, so a long probe can show progress."""
    for company in companies:
        yield kept(company, find_board(company, check), stores, now)


Found = Board | SourceUnavailableError | None


def find_board(company: Company, check: BoardCheck) -> Found:
    """The first likely board that's the company's, None when there's none, or why it couldn't
    tell. Finding only asks the outside world, so several companies can be probed at once."""
    candidates = board_candidates(company.name)
    try:
        return next((board for board in candidates if check.exists(board, company.name)), None)
    except SourceUnavailableError as error:
        return error


def kept(company: Company, found: Found, stores: ProbeStores, now: datetime) -> ProbeResult:
    """What a probe found, stored: the board as live, and the company as probed. A company that
    couldn't be probed isn't logged, so it's tried again next time."""
    if isinstance(found, SourceUnavailableError):
        return ProbeResult(company=company.name, board=None, error=str(found))
    if found:
        stores.companies.save(company.with_board(found).checked(found, FeedStatus.LIVE))
    stores.log.record(company.key, now)
    return ProbeResult(company=company.name, board=found)
