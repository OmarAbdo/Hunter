from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from hunter.adapters.storage.database import open_database
from hunter.adapters.storage.pool import Pool
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import EmployerRef, Employment, Posting, SourceRef

SEEN = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
GREENHOUSE = Posting(
    title="Senior Backend Engineer (m/w/d)",
    company="Nextcloud GmbH",
    location=Location(
        country="DE", city="Berlin", workplace=Workplace.REMOTE, remote_scope=frozenset({"EU"})
    ),
    source=SourceRef(source="greenhouse", native_id="4711"),
    employer=EmployerRef(ats="greenhouse", board="nextcloud", job_id="4711"),
    employment=Employment.FULL_TIME,
    url="https://job-boards.greenhouse.io/nextcloud/jobs/4711",
    description="Build the backend.",
    posted_at=datetime(2026, 10, 20, tzinfo=UTC),
)
INDEED = replace(
    GREENHOUSE,
    title="Senior Backend Engineer (all genders)",
    company="Nextcloud",
    source=SourceRef(source="indeed-alert", native_id="c7ce5aa8dcb2f774"),
    employer=None,
    description="",
)


def test_a_new_posting_becomes_a_new_job(tmp_path: Path) -> None:
    pool = Pool(open_database(tmp_path / "hunter.db"))
    added = pool.add(GREENHOUSE, SEEN)
    assert added.is_new
    assert pool.posting(added.job_id) == GREENHOUSE


def test_the_same_posting_again_is_the_same_job(tmp_path: Path) -> None:
    pool = Pool(open_database(tmp_path / "hunter.db"))
    first = pool.add(GREENHOUSE, SEEN)
    again = pool.add(GREENHOUSE, SEEN)
    assert (again.job_id, again.is_new) == (first.job_id, False)
    assert pool.sightings(first.job_id) == [GREENHOUSE.source]


def test_another_source_showing_the_same_job_adds_a_sighting(tmp_path: Path) -> None:
    pool = Pool(open_database(tmp_path / "hunter.db"))
    first = pool.add(GREENHOUSE, SEEN)
    alert = pool.add(INDEED, SEEN)
    assert (alert.job_id, alert.is_new) == (first.job_id, False)
    assert pool.sightings(first.job_id) == [GREENHOUSE.source, INDEED.source]


def test_a_job_board_posting_learns_its_employer_posting_later(tmp_path: Path) -> None:
    pool = Pool(open_database(tmp_path / "hunter.db"))
    alert = pool.add(INDEED, SEEN)
    employer = pool.add(GREENHOUSE, SEEN)
    assert employer.job_id == alert.job_id
    assert pool.posting(alert.job_id).employer == GREENHOUSE.employer


def test_different_jobs_stay_apart(tmp_path: Path) -> None:
    pool = Pool(open_database(tmp_path / "hunter.db"))
    other = replace(
        GREENHOUSE,
        title="Frontend Engineer",
        source=SourceRef(source="greenhouse", native_id="4712"),
        employer=EmployerRef(ats="greenhouse", board="nextcloud", job_id="4712"),
    )
    assert pool.add(GREENHOUSE, SEEN).job_id != pool.add(other, SEEN).job_id
    assert pool.job_count() == 2


def test_a_job_keeps_all_its_places(tmp_path: Path) -> None:
    pool = Pool(open_database(tmp_path / "hunter.db"))
    several = replace(GREENHOUSE, other_locations=(Location(country="AT", city="Vienna"),))
    assert pool.posting(pool.add(several, SEEN).job_id) == several


def test_a_job_keeps_its_quick_apply_mark(tmp_path: Path) -> None:
    pool = Pool(open_database(tmp_path / "hunter.db"))
    quick = replace(INDEED, quick_apply=True)
    assert pool.posting(pool.add(quick, SEEN).job_id).quick_apply


def test_the_database_writes_ahead_so_commits_stay_cheap(tmp_path: Path) -> None:
    database = open_database(tmp_path / "hunter.db")
    assert database.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_the_pool_survives_a_restart(tmp_path: Path) -> None:
    job_id = Pool(open_database(tmp_path / "hunter.db")).add(GREENHOUSE, SEEN).job_id
    assert Pool(open_database(tmp_path / "hunter.db")).posting(job_id) == GREENHOUSE
