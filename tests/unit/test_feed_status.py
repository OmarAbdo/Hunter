from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from hunter.application.discover import Stores, discover
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.boards import Board, board_from_key
from hunter.domain.discovery.campaign import Rejection
from hunter.domain.discovery.company import Company, FeedStatus
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.pooled import Pooled
from hunter.domain.discovery.posting import Posting, SourceRef

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
BOARD = Board(ats="greenhouse", slug="nextcloud")
JOB = Posting(
    title="Backend Engineer",
    company="Nextcloud",
    location=Location(country="DE", city="Berlin"),
    source=SourceRef(source="greenhouse", native_id="1"),
)


@dataclass
class Feed:
    name: str
    postings: list[Posting] = field(default_factory=list)
    failure: SourceUnavailableError | None = None

    def fetch(self) -> Iterable[Posting]:
        if self.failure:
            raise self.failure
        return self.postings


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


def status_after(feed: Feed) -> FeedStatus:
    companies = Companies(Company(name="Nextcloud").with_board(BOARD))
    discover([feed], [], Stores(jobs=Jobs(), companies=companies, matches=Verdicts()), NOW)
    company = companies.get("nextcloud")
    assert company is not None
    return company.feed_status(BOARD)


def test_a_board_with_jobs_is_live() -> None:
    assert status_after(Feed("greenhouse:nextcloud", [JOB])) is FeedStatus.LIVE


def test_a_board_without_jobs_is_empty() -> None:
    assert status_after(Feed("greenhouse:nextcloud")) is FeedStatus.EMPTY


def test_a_board_that_is_not_there_is_gone() -> None:
    gone = SourceUnavailableError("HTTP 404", gone=True)
    assert status_after(Feed("greenhouse:nextcloud", failure=gone)) is FeedStatus.GONE


def test_a_board_that_is_down_for_now_keeps_its_status() -> None:
    down = SourceUnavailableError("HTTP 503")
    assert status_after(Feed("greenhouse:nextcloud", failure=down)) is FeedStatus.UNCHECKED


def test_sources_that_are_not_boards_change_no_company() -> None:
    companies = Companies(Company(name="Nextcloud").with_board(BOARD))
    discover([Feed("indeed-alert", [JOB])], [], Stores(Jobs(), companies, Verdicts()), NOW)
    assert companies.saved["nextcloud"].feed_status(BOARD) is FeedStatus.UNCHECKED


def test_a_board_key_names_its_board() -> None:
    assert board_from_key("workday:nvidia/wd5/NVIDIAExternalCareerSite") == Board(
        ats="workday", slug="nvidia/wd5/NVIDIAExternalCareerSite"
    )
    assert board_from_key("indeed-alert") is None
