from datetime import UTC, datetime
from pathlib import Path

from hunter.adapters.database import open_database
from hunter.adapters.matches import Matches
from hunter.domain.discovery.campaign import Rejection

DECIDED = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def test_matched_jobs_are_listed_per_campaign(tmp_path: Path) -> None:
    matches = Matches(open_database(tmp_path / "hunter.db"))
    matches.record(1, "de-swe-berlin", None, DECIDED)
    matches.record(2, "de-swe-berlin", Rejection.PLACE, DECIDED)
    matches.record(3, "ae-onsite", None, DECIDED)
    assert matches.matched("de-swe-berlin") == [1]


def test_rejections_are_counted_by_reason(tmp_path: Path) -> None:
    matches = Matches(open_database(tmp_path / "hunter.db"))
    matches.record(1, "de-swe-berlin", Rejection.PLACE, DECIDED)
    matches.record(2, "de-swe-berlin", Rejection.PLACE, DECIDED)
    matches.record(3, "de-swe-berlin", Rejection.ROLE, DECIDED)
    assert matches.rejections("de-swe-berlin") == {Rejection.PLACE: 2, Rejection.ROLE: 1}


def test_a_new_verdict_replaces_the_old_one(tmp_path: Path) -> None:
    matches = Matches(open_database(tmp_path / "hunter.db"))
    matches.record(1, "de-swe-berlin", Rejection.PLACE, DECIDED)
    matches.record(1, "de-swe-berlin", None, DECIDED)
    assert matches.matched("de-swe-berlin") == [1]
    assert matches.rejections("de-swe-berlin") == {}


def test_a_job_already_decided_for_a_campaign_is_known(tmp_path: Path) -> None:
    matches = Matches(open_database(tmp_path / "hunter.db"))
    matches.record(1, "de-swe-berlin", Rejection.ROLE, DECIDED)
    assert matches.decided(1, "de-swe-berlin")
    assert not matches.decided(1, "ae-onsite")
