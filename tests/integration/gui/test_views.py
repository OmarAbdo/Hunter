from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from hunter.adapters.gui.views import (
    campaigns_view,
    companies_view,
    jobs_view,
    pool_view,
)
from hunter.adapters.gui.run_views import held_view, runs_view
from hunter.adapters.storage.holds import Holds
from hunter.adapters.storage.run_log import RunLog
from hunter.application.discover import SourceReport
from hunter.adapters.storage.database import open_database
from hunter.adapters.storage.matches import Matches
from hunter.adapters.storage.pool import Pool
from hunter.adapters.storage.registry import Registry
from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.campaign import Campaign, Rejection
from hunter.domain.discovery.company import Company, FeedStatus
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import EmployerRef, Employment, Posting, SourceRef

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
BERLIN = Campaign(id="berlin", title="Software in Berlin", home="DE", countries=frozenset({"DE"}))
TAKEN = Posting(
    title="Senior Backend Engineer",
    company="N26",
    location=Location(country="DE", city="Berlin", workplace=Workplace.HYBRID),
    source=SourceRef(source="greenhouse", native_id="1"),
    employer=EmployerRef(ats="greenhouse", board="n26", job_id="1"),
    employment=Employment.FULL_TIME,
    url="https://job-boards.greenhouse.io/n26/jobs/1",
    posted_at=datetime(2026, 10, 20, tzinfo=UTC),
)
TURNED_DOWN = Posting(
    title="Account Executive",
    company="N26",
    location=Location(country="DE", city="Berlin"),
    source=SourceRef(source="greenhouse", native_id="2"),
)


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "hunter.db"
    database = open_database(path)
    pool, matches = Pool(database), Matches(database)
    taken = pool.add(TAKEN, NOW).job_id
    pool.add(replace_source(TAKEN, "indeed-alert", "abc"), NOW)  # the same job, seen again
    matches.record(taken, "berlin", None, NOW)
    matches.record(pool.add(TURNED_DOWN, NOW).job_id, "berlin", Rejection.ROLE, NOW)
    board = Board(ats="greenhouse", slug="n26")
    company = Company(name="N26").with_board(board).checked(board, FeedStatus.LIVE)
    Registry(database).save(company.with_website("https://n26.com"))
    return path


def replace_source(posting: Posting, source: str, native_id: str) -> Posting:
    return Posting(
        title=posting.title,
        company=posting.company,
        location=posting.location,
        source=SourceRef(source=source, native_id=native_id),
    )


def test_each_campaign_shows_what_it_took_and_why_it_turned_jobs_down(database_path: Path) -> None:
    [berlin] = campaigns_view(open_database(database_path), [BERLIN])
    assert berlin == {
        "id": "berlin",
        "title": "Software in Berlin",
        "taken": 1,
        "turned_down": {"role": 1},
    }


def test_a_campaign_s_jobs_come_with_where_they_were_seen(database_path: Path) -> None:
    [job] = jobs_view(open_database(database_path), "berlin")
    assert job["title"] == "Senior Backend Engineer"
    assert job["company"] == "N26"
    assert job["places"] == ["Berlin, DE"]
    assert (job["workplace"], job["employment"]) == ("hybrid", "full-time")
    assert job["posted_at"] == "2026-10-20"
    assert job["url"] == "https://job-boards.greenhouse.io/n26/jobs/1"
    assert job["employer_system"] == "greenhouse"
    assert job["sources"] == ["greenhouse", "indeed-alert"]


def test_companies_show_their_boards_and_website(database_path: Path) -> None:
    [n26] = companies_view(open_database(database_path))
    assert n26 == {
        "name": "N26",
        "website": "https://n26.com",
        "boards": [{"board": "greenhouse:n26", "status": "live"}],
    }


def test_the_pool_is_counted(database_path: Path) -> None:
    assert pool_view(open_database(database_path)) == {"jobs": 2, "companies": 1, "boards": 1}


def test_the_latest_runs_come_with_what_each_source_brought(database_path: Path) -> None:
    database = open_database(database_path)
    runs = RunLog(database, clock=lambda: NOW)
    run = runs.start(["berlin"])
    runs.record(run.run_id, SourceReport("greenhouse:n26", 3, 2, {"berlin": 1}))
    runs.record(run.run_id, SourceReport("greenhouse:gone", error="HTTP 404"))
    runs.finish(run.run_id, linked_jobs=4)
    [shown] = runs_view(database)
    # In UTC; the page shows them in the computer's own time.
    assert shown["started_at"] == shown["ended_at"] == "2026-10-26T12:00:00+00:00"
    assert (shown["fetched"], shown["new"], shown["taken"], shown["failed"]) == (3, 2, 1, 1)
    assert shown["linked"] == 4
    assert shown["sources"] == [
        {"source": "greenhouse:n26", "fetched": 3, "new": 2, "taken": 1, "error": None},
        {"source": "greenhouse:gone", "fetched": 0, "new": 0, "taken": 0, "error": "HTTP 404"},
    ]


def test_the_sites_holding_hunter_off_come_with_when_their_pause_ends(database_path: Path) -> None:
    database = open_database(database_path)
    Holds(database).save("api.lever.co", NOW - timedelta(hours=1))
    Holds(database).save("apply.workable.com", NOW + timedelta(hours=21))
    assert held_view(database, clock=lambda: NOW) == [
        {"host": "apply.workable.com", "until": "2026-10-27T09:00:00+00:00"}
    ]
