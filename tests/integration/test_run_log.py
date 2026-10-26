from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hunter.adapters.storage.database import open_database
from hunter.adapters.storage.run_log import DiscoveryRun, RunLog
from hunter.application.discover import SourceReport

STARTED = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)
N26 = SourceReport("greenhouse:n26", fetched=3, new_jobs=2, taken={"de-swe-berlin": 1})
GONE = SourceReport("greenhouse:gone", error="HTTP 404")


def ticking() -> Callable[[], datetime]:
    """A clock that moves a minute on each reading."""
    times = (STARTED + timedelta(minutes=minute) for minute in range(100))
    return lambda: next(times)


def test_a_finished_run_comes_back_with_its_times_campaigns_and_links(tmp_path: Path) -> None:
    log = RunLog(open_database(tmp_path / "hunter.db"), clock=ticking())
    run = log.start(["de-swe-berlin", "ae-onsite"])
    log.finish(run.run_id, linked_jobs=4)
    assert run == DiscoveryRun(run.run_id, STARTED, None, ("de-swe-berlin", "ae-onsite"), 0)
    assert log.latest(10) == [
        DiscoveryRun(
            run.run_id,
            STARTED,
            STARTED + timedelta(minutes=1),
            ("de-swe-berlin", "ae-onsite"),
            4,
        )
    ]


def test_a_run_keeps_each_source_in_the_order_it_was_read(tmp_path: Path) -> None:
    log = RunLog(open_database(tmp_path / "hunter.db"), clock=ticking())
    run = log.start(["de-swe-berlin"])
    log.record(run.run_id, GONE)
    log.record(run.run_id, N26)
    assert log.reports(run.run_id) == [GONE, N26]


def test_a_run_shows_only_its_own_sources(tmp_path: Path) -> None:
    log = RunLog(open_database(tmp_path / "hunter.db"), clock=ticking())
    first, second = log.start(["de-swe-berlin"]), log.start(["de-swe-berlin"])
    log.record(first.run_id, N26)
    log.record(second.run_id, GONE)
    assert log.reports(first.run_id) == [N26]
    assert log.reports(second.run_id) == [GONE]


def test_the_latest_runs_come_newest_first_up_to_the_limit(tmp_path: Path) -> None:
    log = RunLog(open_database(tmp_path / "hunter.db"), clock=ticking())
    runs = [log.start([campaign]) for campaign in ("first", "second", "third")]
    latest = log.latest(2)
    assert [run.run_id for run in latest] == [runs[2].run_id, runs[1].run_id]
    assert [run.campaign_ids for run in latest] == [("third",), ("second",)]


def test_a_stopped_run_keeps_what_it_read_and_has_no_end(tmp_path: Path) -> None:
    stopped = RunLog(open_database(tmp_path / "hunter.db"), clock=ticking())
    stopped.record(stopped.start(["de-swe-berlin"]).run_id, N26)
    log = RunLog(open_database(tmp_path / "hunter.db"))
    [run] = log.latest(10)
    assert run.ended_at is None
    assert run.linked_jobs == 0
    assert log.reports(run.run_id) == [N26]


def test_runs_are_timed_by_the_real_clock_unless_given_one(tmp_path: Path) -> None:
    before = datetime.now(UTC)
    run = RunLog(open_database(tmp_path / "hunter.db")).start([])
    assert before <= run.started_at <= datetime.now(UTC)
    assert run.campaign_ids == ()
