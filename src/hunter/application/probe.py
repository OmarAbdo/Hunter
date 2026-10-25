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
        yield probed(company, check, stores, now)


def probed(company: Company, check: BoardCheck, stores: ProbeStores, now: datetime) -> ProbeResult:
    try:
        found = next(
            (board for board in board_candidates(company.name) if check.exists(board)), None
        )
    except SourceUnavailableError as error:
        return ProbeResult(company=company.name, board=None, error=str(error))
    if found:
        stores.companies.save(company.with_board(found).checked(found, FeedStatus.LIVE))
    stores.log.record(company.key, now)
    return ProbeResult(company=company.name, board=found)
