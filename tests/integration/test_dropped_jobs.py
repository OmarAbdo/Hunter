"""Jobs that drop off their employer's board: gone once a run read the board in full without
them, open again once the board lists them again."""

import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hunter.adapters.storage.database import open_database
from hunter.adapters.storage.matches import Matches
from hunter.adapters.storage.pool import Ads, Pool
from hunter.adapters.storage.run_log import RunLog
from hunter.application.discover import SourceReport
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

SEEN = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
GREENHOUSE = Posting(
    title="Senior Backend Engineer (m/w/d)",
    company="Nextcloud GmbH",
    location=Location(country="DE", city="Berlin"),
    source=SourceRef(source="greenhouse", native_id="4711"),
    employer=EmployerRef(ats="greenhouse", board="nextcloud", job_id="4711"),
    description="Build the backend.",
)

BOARD = "greenhouse:nextcloud"
EARLIER = SEEN - timedelta(days=1)


def run_reading(database: sqlite3.Connection, report: SourceReport) -> int:
    """A discovery run that started at SEEN and read one source."""
    log = RunLog(database, clock=lambda: SEEN)
    run = log.start(["berlin"])
    log.record(run.run_id, report)
    return run.run_id


def on_the_board(database: sqlite3.Connection, job: Posting, seen: datetime) -> int:
    job_id = Pool(database).add(job, seen).job_id
    Matches(database).record(job_id, "berlin", None, seen)
    return job_id


def test_a_job_its_board_no_longer_lists_is_gone(tmp_path: Path) -> None:
    database = open_database(tmp_path / "hunter.db")
    dropped = on_the_board(database, GREENHOUSE, EARLIER)
    other = replace(GREENHOUSE, title="Data Engineer", source=SourceRef("greenhouse", "4712"))
    listed = on_the_board(
        database, replace(other, employer=EmployerRef("greenhouse", "nextcloud", "4712")), SEEN
    )
    run_id = run_reading(database, SourceReport(BOARD, fetched=1))
    assert Ads(database).mark_dropped(run_id, {}, SEEN) == 1
    gone = {job.posting.title: job.gone for job in Pool(database).taken()}
    assert gone == {GREENHOUSE.title: True, "Data Engineer": False}
    assert listed != dropped


def test_a_board_read_in_part_or_not_at_all_says_nothing_of_its_jobs(tmp_path: Path) -> None:
    """A list at its feed's cut-off may have left the job out; so may a failed or empty read."""
    database = open_database(tmp_path / "hunter.db")
    on_the_board(database, GREENHOUSE, EARLIER)
    for report in (
        SourceReport(BOARD, fetched=200),
        SourceReport(BOARD, error="boards-api.greenhouse.io: HTTP 503"),
        SourceReport(BOARD, fetched=0),
    ):
        run_id = run_reading(database, report)
        assert Ads(database).mark_dropped(run_id, {"greenhouse": 200}, SEEN) == 0
    assert not Pool(database).taken()[0].gone


def test_a_gone_job_its_board_lists_again_is_open_again(tmp_path: Path) -> None:
    database = open_database(tmp_path / "hunter.db")
    job_id = on_the_board(database, GREENHOUSE, EARLIER)
    Ads(database).mark_gone(job_id, EARLIER)
    Pool(database).add(GREENHOUSE, SEEN)
    assert not Pool(database).taken()[0].gone
