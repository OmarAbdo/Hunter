"""What discovery needs from the outside world. Adapters provide these; the use cases only know
them by these shapes."""

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.campaign import Rejection
from hunter.domain.discovery.company import Company
from hunter.domain.discovery.pooled import Pooled
from hunter.domain.discovery.posting import Posting


class SourceUnavailableError(Exception):
    """A source that couldn't be read this time: down, refusing, or answering nonsense. `gone`
    says it isn't there at all (HTTP 404 or 410): a board that moved or closed."""

    def __init__(self, message: str, *, gone: bool = False) -> None:
        super().__init__(message)
        self.gone = gone


class JobSource(Protocol):
    @property
    def name(self) -> str: ...

    def fetch(self) -> Iterable[Posting]:
        """Every posting the source shows now. Raises SourceUnavailableError."""
        ...


class JobStore(Protocol):
    def add(self, posting: Posting, seen_at: datetime) -> Pooled: ...


class CompanyStore(Protocol):
    def get(self, key: str) -> Company | None: ...

    def save(self, company: Company) -> None: ...

    def owner_of(self, board: Board) -> Company | None: ...


class MatchStore(Protocol):
    def decided(self, job_id: int, campaign_id: str) -> bool: ...

    def record(
        self, job_id: int, campaign_id: str, rejection: Rejection | None, decided_at: datetime
    ) -> None: ...


class BoardCheck(Protocol):
    def exists(self, board: Board, company: str) -> bool:
        """Whether the board is there with the company's jobs. Raises SourceUnavailableError when
        it can't tell."""
        ...


class ProbeLog(Protocol):
    def record(self, company_key: str, probed_at: datetime) -> None: ...


class JobLinks(Protocol):
    def unresolved(self) -> list[tuple[int, Posting]]:
        """The jobs not yet known from the employer's own system, by id."""
        ...

    def employer_jobs(self, company_key: str) -> list[tuple[int, Posting]]:
        """The jobs on the boards of the company, by id."""
        ...

    def merge(self, job_id: int, into: int) -> None: ...


class CareersPages(Protocol):
    def links(self, website: str) -> list[str]:
        """Every link on the website's home page and on its own careers pages; none when the site
        can't be read."""
        ...


class AdReader(Protocol):
    def read(self, posting: Posting) -> str:
        """The job's whole ad, from the source that showed it. Raises SourceUnavailableError,
        `gone` when the source doesn't have the job any more."""
        ...


class AdStore(Protocol):
    def wanting(self) -> list[tuple[int, Posting]]:
        """The jobs a campaign took that lack their whole ad and aren't known to be gone, by id,
        the newest first."""
        ...

    def keep_ad(self, job_id: int, posting: Posting) -> None: ...

    def mark_gone(self, job_id: int, gone_at: datetime) -> None: ...


class WebSearch(Protocol):
    def links(self, query: str) -> list[str]:
        """The links a web search finds, best first. Raises SourceUnavailableError."""
        ...
