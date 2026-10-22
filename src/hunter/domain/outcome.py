"""The one number Hunter exists to move: applications submitted with proof, per hour it ran, over
its last three running hours. Days it doesn't run don't count; with less than three hours run, the
number is still divided by three, so a short lucky session can't make it look better than it is."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

WINDOW = timedelta(hours=3)
HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class Session:
    """One stretch of time Hunter was running."""

    started: datetime
    ended: datetime

    def __post_init__(self) -> None:
        if self.ended < self.started:
            raise ValueError(f"A session that ends before it starts: {self}")

    def holds(self, moment: datetime) -> bool:
        return self.started <= moment <= self.ended


@dataclass(frozen=True)
class Submission:
    """One application Hunter sent; it counts only with proof that it arrived."""

    sent: datetime
    proven: bool


def counted_sessions(sessions: Sequence[Session], window: timedelta = WINDOW) -> list[Session]:
    """The newest sessions that add up to `window` of running time, the oldest one cut to fit."""
    counted: list[Session] = []
    remaining = window
    for session in sorted(sessions, key=lambda each: each.ended, reverse=True):
        if remaining <= timedelta(0):
            break
        start = max(session.started, session.ended - remaining)
        counted.append(Session(started=start, ended=session.ended))
        remaining -= session.ended - start
    return counted


def applications_per_hour(
    sessions: Sequence[Session], submissions: Sequence[Submission], window: timedelta = WINDOW
) -> float:
    counted = counted_sessions(sessions, window)
    proven = [
        submission
        for submission in submissions
        if submission.proven and any(session.holds(submission.sent) for session in counted)
    ]
    return len(proven) / (window / HOUR)
