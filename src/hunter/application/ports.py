"""What discovery needs from the outside world. Adapters provide these; the use cases only know
them by these shapes."""

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

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


class MatchStore(Protocol):
    def decided(self, job_id: int, campaign_id: str) -> bool: ...

    def record(
        self, job_id: int, campaign_id: str, rejection: Rejection | None, decided_at: datetime
    ) -> None: ...
