from collections.abc import Iterable
from datetime import UTC, datetime

from hunter.application.discover import Stores, discover
from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.campaign import Rejection
from hunter.domain.discovery.company import Company
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.pooled import Pooled
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
BOARD = Board(ats="personio", slug="1komma5grad.de")
JOB = Posting(
    title="Software Engineer",
    company="1KOMMA5° Heat GmbH",
    location=Location(country="DE"),
    source=SourceRef(source="personio", native_id="1"),
    employer=EmployerRef(ats="personio", board="1komma5grad.de", job_id="1"),
)


class Feed:
    name = "personio:1komma5grad.de"

    def fetch(self) -> Iterable[Posting]:
        return [JOB]


class Jobs:
    def add(self, posting: Posting, seen_at: datetime) -> Pooled:
        return Pooled(job_id=1, is_new=True)


class Companies:
    def __init__(self, *companies: Company) -> None:
        self.saved = {company.key: company for company in companies}

    def get(self, key: str) -> Company | None:
        return self.saved.get(key)

    def save(self, company: Company) -> None:
        self.saved[company.key] = company

    def owner_of(self, board: Board) -> Company | None:
        return next((company for company in self.saved.values() if board in company.feeds), None)


class Verdicts:
    def decided(self, job_id: int, campaign_id: str) -> bool:
        return False

    def record(
        self, job_id: int, campaign_id: str, rejection: Rejection | None, decided_at: datetime
    ) -> None:
        return


def test_a_posting_named_differently_from_its_boards_owner_joins_that_owner() -> None:
    companies = Companies(Company(name="1KOMMA5°").with_board(BOARD))
    discover([Feed()], [], Stores(Jobs(), companies, Verdicts()), NOW)
    assert list(companies.saved) == [Company(name="1KOMMA5°").key]


def test_a_posting_from_an_unknown_board_still_registers_its_company() -> None:
    companies = Companies()
    discover([Feed()], [], Stores(Jobs(), companies, Verdicts()), NOW)
    assert [company.name for company in companies.saved.values()] == ["1KOMMA5° Heat GmbH"]
