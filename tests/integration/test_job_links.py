from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hunter.adapters.storage.database import open_database
from hunter.adapters.storage.job_links import JobLinks
from hunter.adapters.storage.matches import Matches
from hunter.adapters.storage.pool import Pool
from hunter.adapters.storage.registry import Registry
from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.company import Company
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

SEEN = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
EMPLOYER = Posting(
    title="Senior Backend Engineer",
    company="N26",
    location=Location(country="DE", city="Berlin"),
    source=SourceRef(source="greenhouse", native_id="4711"),
    employer=EmployerRef(ats="greenhouse", board="n26", job_id="4711"),
)
INDEED = replace(
    EMPLOYER,
    company="N26 GmbH",
    location=Location(country="DE"),
    source=SourceRef(source="indeed-alert", native_id="abc123"),
    employer=None,
)


@pytest.fixture
def stores(tmp_path: Path) -> tuple[Pool, JobLinks, Matches]:
    database = open_database(tmp_path / "hunter.db")
    Registry(database).save(Company(name="N26").with_board(Board(ats="greenhouse", slug="n26")))
    return Pool(database), JobLinks(database), Matches(database)


def test_jobs_seen_only_on_job_boards_are_unresolved(
    stores: tuple[Pool, JobLinks, Matches],
) -> None:
    pool, links, _ = stores
    pool.add(EMPLOYER, SEEN)
    seen = pool.add(INDEED, SEEN)
    assert links.unresolved() == [(seen.job_id, INDEED)]


def test_employer_jobs_are_the_jobs_on_the_company_s_boards(
    stores: tuple[Pool, JobLinks, Matches],
) -> None:
    pool, links, _ = stores
    employer = pool.add(EMPLOYER, SEEN)
    pool.add(replace(EMPLOYER, employer=EmployerRef("greenhouse", "n26x", "1")), SEEN)
    assert links.employer_jobs("n26") == [(employer.job_id, EMPLOYER)]
    assert links.employer_jobs("nowhere") == []


def test_a_merged_job_keeps_its_sightings_on_the_employer_job(
    stores: tuple[Pool, JobLinks, Matches],
) -> None:
    pool, links, matches = stores
    employer, seen = pool.add(EMPLOYER, SEEN), pool.add(INDEED, SEEN)
    matches.record(seen.job_id, "de-swe-berlin", None, SEEN)
    links.merge(seen.job_id, into=employer.job_id)
    assert [ref.source for ref in pool.sightings(employer.job_id)] == ["greenhouse", "indeed-alert"]
    assert links.unresolved() == []
    assert not matches.decided(seen.job_id, "de-swe-berlin")
    assert pool.job_count() == 1
