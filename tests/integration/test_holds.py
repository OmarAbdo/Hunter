import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hunter.adapters.storage.database import open_database
from hunter.adapters.storage.holds import Holds, kept_pacing
from hunter.domain.pacing import Moment, PaceRule

NOON = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
HOUR = timedelta(hours=1)
PACE = PaceRule(min_gap=timedelta(seconds=1))


def test_a_pause_comes_back_until_it_ends(tmp_path: Path) -> None:
    holds = Holds(open_database(tmp_path / "hunter.db"))
    holds.save("apply.workable.com", NOON + HOUR)
    holds.save("api.lever.co", NOON)
    assert holds.current(NOON) == {"apply.workable.com": NOON + HOUR}
    assert holds.current(NOON + HOUR) == {}


def test_the_later_of_two_pauses_is_kept(tmp_path: Path) -> None:
    holds = Holds(open_database(tmp_path / "hunter.db"))
    holds.save("apply.workable.com", NOON + 2 * HOUR)
    holds.save("apply.workable.com", NOON + HOUR)
    assert holds.current(NOON) == {"apply.workable.com": NOON + 2 * HOUR}


def test_a_pause_asked_for_in_one_run_holds_in_the_next(tmp_path: Path) -> None:
    def connect() -> sqlite3.Connection:
        return open_database(tmp_path / "hunter.db")

    later = datetime.now(UTC) + HOUR
    kept_pacing({}, PACE, connect).hold("apply.workable.com", later)
    next_run = kept_pacing({}, PACE, connect)
    now = Moment(wall=later - HOUR, steady=0)
    assert next_run.wait("apply.workable.com", now) == HOUR
