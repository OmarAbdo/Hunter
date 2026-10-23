from datetime import UTC, datetime, timedelta

import pytest

from hunter.domain.outcome import Session, Submission, applications_per_hour

START = datetime(2026, 10, 23, 9, 0, tzinfo=UTC)


def at(hours: float) -> datetime:
    return START + timedelta(hours=hours)


def session(start: float, end: float) -> Session:
    return Session(started=at(start), ended=at(end))


def sent(*hours: float, proven: bool = True) -> list[Submission]:
    return [Submission(sent=at(hour), proven=proven) for hour in hours]


def test_no_sessions_is_zero() -> None:
    assert applications_per_hour([], sent(1)) == 0


def test_proven_submissions_in_three_running_hours() -> None:
    assert applications_per_hour([session(0, 3)], sent(0.5, 1, 1.5, 2, 2.5, 2.9)) == 2


def test_unproven_submissions_do_not_count() -> None:
    submissions = sent(1, 2) + sent(1.5, proven=False)
    assert applications_per_hour([session(0, 3)], submissions) == pytest.approx(2 / 3)


def test_submissions_outside_sessions_do_not_count() -> None:
    assert applications_per_hour([session(0, 3)], sent(-1, 4)) == 0


def test_session_edges_count() -> None:
    assert applications_per_hour([session(0, 3)], sent(0, 3)) == pytest.approx(2 / 3)


def test_newest_sessions_fill_the_window_and_the_oldest_is_cut() -> None:
    old, new = session(0, 2), session(24, 26)
    submissions = sent(0.5, 1.5, 24.5, 25, 25.5)
    assert applications_per_hour([new, old], submissions) == pytest.approx(4 / 3)


def test_sessions_beyond_the_window_do_not_count() -> None:
    sessions = [session(0, 1), session(10, 13)]
    assert applications_per_hour(sessions, sent(0.5, 11)) == pytest.approx(1 / 3)


def test_less_than_three_hours_is_still_divided_by_three() -> None:
    assert applications_per_hour([session(0, 1)], sent(0.2, 0.4, 0.6)) == 1


def test_a_session_cannot_end_before_it_starts() -> None:
    with pytest.raises(ValueError, match="ends before it starts"):
        session(2, 1)
