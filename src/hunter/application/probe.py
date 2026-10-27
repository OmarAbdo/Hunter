"""Probing: finding the board of a company Hunter knows only by name (seen in an Indeed alert, say),
so its jobs can come from the employer's own system from then on. Where the company's website is
known, the boards its home and careers pages link to are tried first; then likely board names on
every system that can be guessed; last, the boards a web search finds. A company is probed once
and logged, found or not, and once more when it gains a website; one that couldn't be probed (a
site didn't answer) is tried again later."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from itertools import chain

from hunter.application.ports import (
    BoardCheck,
    CareersPages,
    CompanyStore,
    ProbeLog,
    SourceUnavailableError,
    WebSearch,
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


def find_board(
    company: Company,
    check: BoardCheck,
    pages: CareersPages | None = None,
    search: WebSearch | None = None,
) -> Found:
    """The first board that's the company's, None when there's none, or why it couldn't tell.
    Finding only asks the outside world, so several companies can be probed at once."""
    tried = candidates(company, pages, search)
    try:
        return next((board for board in tried if check.exists(board, company.name)), None)
    except SourceUnavailableError as error:
        return error


def candidates(
    company: Company, pages: CareersPages | None, search: WebSearch | None
) -> Iterator[Board]:
    """Each board to try, once, in order: those the website links to, the likely names, and last
    those a web search finds. The search costs quota, so it's made only when the others failed."""
    tried: set[Board] = set()
    found = chain(linked_boards(company, pages), board_candidates(company.name))
    for board in chain(found, searched_boards(company, search)):
        if board not in tried:
            tried.add(board)
            yield board


def linked_boards(company: Company, pages: CareersPages | None) -> list[Board]:
    """The boards the company's website links to, each once."""
    if not company.website or pages is None:
        return []
    return boards_in(pages.links(company.website))


def searched_boards(company: Company, search: WebSearch | None) -> Iterator[Board]:
    """The boards a web search for the company's jobs finds, in the order of its results."""
    if search is not None:
        yield from boards_in(search.links(f'"{company.name}" careers jobs'))


def boards_in(links: list[str]) -> list[Board]:
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
