import threading
from collections.abc import Iterable
from datetime import UTC, datetime

from hunter.application.discover import Stores, discover_each
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.campaign import Rejection
from hunter.domain.discovery.company import Company
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.pooled import Pooled
from hunter.domain.discovery.posting import Posting, SourceRef

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def posting(native_id: str) -> Posting:
    return Posting(
        title="Backend Engineer",
        company="Nextcloud",
        location=Location(country="DE"),
        source=SourceRef(source="greenhouse", native_id=native_id),
    )


class Meeting:
    """A source that only answers once the other one is being read at the same time."""

    def __init__(self, name: str, meeting: threading.Barrier) -> None:
        self.name = name
        self.meeting = meeting

    def fetch(self) -> Iterable[Posting]:
        try:
            self.meeting.wait(timeout=5)
        except threading.BrokenBarrierError as error:
            raise SourceUnavailableError(f"{self.name} was read alone") from error
        return [posting(self.name)]


class Jobs:
    def __init__(self) -> None:
        self.added_by: set[str] = set()

    def add(self, added: Posting, seen_at: datetime) -> Pooled:
        self.added_by.add(threading.current_thread().name)
        return Pooled(job_id=1, is_new=True)


class Companies:
    def get(self, key: str) -> Company | None:
        return None

    def save(self, company: Company) -> None:
        return

    def owner_of(self, board: Board) -> Company | None:
        return None


class Verdicts:
    def decided(self, job_id: int, campaign_id: str) -> bool:
        return False

    def record(
        self, job_id: int, campaign_id: str, rejection: Rejection | None, decided_at: datetime
    ) -> None:
        return


def test_sources_are_read_at_the_same_time_and_reported_in_their_order() -> None:
    meeting = threading.Barrier(2)
    sources = [Meeting("greenhouse:first", meeting), Meeting("ashby:second", meeting)]
    jobs = Jobs()
    reports = list(discover_each(sources, [], Stores(jobs, Companies(), Verdicts()), NOW))
    assert [(report.source, report.error) for report in reports] == [
        ("greenhouse:first", None),
        ("ashby:second", None),
    ]
    assert jobs.added_by == {threading.current_thread().name}
