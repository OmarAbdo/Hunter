"""Probing: finding the board of a company Hunter knows only by name (seen in an Indeed alert, say),
so its jobs can come from the employer's own system from then on. Where the company's website is
known, the boards its home and careers pages link to are tried first; then likely board names on
every system that can be guessed. A company is probed once and logged, found or not, and once more
when it gains a website; one that couldn't be probed (a site didn't answer) is tried again later."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime

from hunter.application.ports import (
    BoardCheck,
    CareersPages,
    CompanyStore,
    ProbeLog,
    SourceUnavailableError,
)
from hunter.domain.discovery.boards import Board, board_from_link
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
    """Each company's result as soon as it's probed, by likely board names only. The command line
    probes several companies at once, with their careers pages, through `find_board` and `kept`."""
    for company in companies:
        yield kept(company, find_board(company, check), stores, now)


Found = Board | SourceUnavailableError | None


def find_board(company: Company, check: BoardCheck, pages: CareersPages | None = None) -> Found:
    """The first board that's the company's, None when there's none, or why it couldn't tell.
    Finding only asks the outside world, so several companies can be probed at once."""
    candidates = [*linked_boards(company, pages), *board_candidates(company.name)]
    try:
        return next((board for board in candidates if check.exists(board, company.name)), None)
    except SourceUnavailableError as error:
        return error


def linked_boards(company: Company, pages: CareersPages | None) -> list[Board]:
    """The boards the company's website links to, each once."""
    if not company.website or pages is None:
        return []
    links = pages.links(company.website)
    return list(dict.fromkeys(board for link in links if (board := board_from_link(link))))


def probe_marks(company: Company) -> list[str]:
    """What the probe log holds for a company once it's probed: its key, and a second mark when
    it was probed with its website, so a company that gains a website is probed once more."""
    return [company.key, *([f"{company.key} website"] if company.website else [])]


def kept(company: Company, found: Found, stores: ProbeStores, now: datetime) -> ProbeResult:
    """What a probe found, stored: the board as live, and the company as probed. A company that
    couldn't be probed isn't logged, so it's tried again next time."""
    if isinstance(found, SourceUnavailableError):
        return ProbeResult(company=company.name, board=None, error=str(found))
    if found and not stores.companies.owner_of(found):  # a board belongs to one company
        stores.companies.save(company.with_board(found).checked(found, FeedStatus.LIVE))
    for mark in probe_marks(company):
        stores.log.record(mark, now)
    return ProbeResult(company=company.name, board=found)
