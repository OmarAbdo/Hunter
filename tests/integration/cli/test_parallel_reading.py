import threading
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

import pytest

from hunter.adapters.cli.parallel_reading import RunControl, RunStoppedError, read_in_parallel
from hunter.application.discover import Stores, take_each
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


class Counted:
    def __init__(self, name: str) -> None:
        self.name = name
        self.reads = 0

    def fetch(self) -> Iterable[Posting]:
        self.reads += 1
        return [posting(self.name)]


def test_a_stopped_run_reads_no_source_it_had_not_started() -> None:
    control = RunControl()
    source = Counted("greenhouse:later")
    control.stop()
    [gated] = control.gated([source])
    with pytest.raises(RunStoppedError):
        list(read_in_parallel([gated]))
    assert (gated.name, source.reads) == ("greenhouse:later", 0)


def test_a_paused_run_starts_no_source_until_it_goes_on() -> None:
    control = RunControl()
    source = Counted("greenhouse:later")
    control.pause()
    [gated] = control.gated([source])
    reading = threading.Thread(target=gated.fetch)
    reading.start()
    reading.join(timeout=0.3)
    assert (control.paused, source.reads) == (True, 0)
    control.resume()
    reading.join(timeout=5)
    assert (control.paused, source.reads) == (False, 1)


def test_stopping_a_paused_run_lets_its_waiting_sources_go() -> None:
    control = RunControl()
    control.pause()
    [gated] = control.gated([Counted("greenhouse:later")])
    errors: list[Exception] = []
    reading = threading.Thread(target=lambda: errors.append(stopped(gated.fetch)))
    reading.start()
    control.stop()
    reading.join(timeout=5)
    assert [type(error) for error in errors] == [RunStoppedError]


def stopped(fetch: Callable[[], object]) -> Exception:
    try:
        fetch()
    except RunStoppedError as error:
        return error
    raise AssertionError("the source was read")


def test_sources_are_read_at_the_same_time_and_reported_in_their_order() -> None:
    meeting = threading.Barrier(2)
    sources = [Meeting("greenhouse:first", meeting), Meeting("ashby:second", meeting)]
    jobs = Jobs()
    readings = read_in_parallel(sources)
    reports = list(take_each(readings, [], Stores(jobs, Companies(), Verdicts()), NOW))
    assert [(report.source, report.error) for report in reports] == [
        ("greenhouse:first", None),
        ("ashby:second", None),
    ]
    assert jobs.added_by == {threading.current_thread().name}
