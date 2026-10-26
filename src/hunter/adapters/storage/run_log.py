"""The run log: what each discovery run brought, source by source, kept so it can be shown after
the run. Each source's report is kept as soon as it's taken in, so a run that was stopped or
crashed keeps what it read until then; such a run has no end time."""

import json
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from hunter.application.discover import SourceReport


@dataclass(frozen=True)
class DiscoveryRun:
    """One run: when it started and ended (None if it never did), the campaigns it was for, and
    how many job-board jobs it linked to the employer's own posting at its end."""

    run_id: int
    started_at: datetime
    ended_at: datetime | None
    campaign_ids: tuple[str, ...]
    linked_jobs: int


def utc_now() -> datetime:
    return datetime.now(UTC)


class RunLog:
    """`clock` times the runs; tests give a fixed one."""

    def __init__(
        self, database: sqlite3.Connection, clock: Callable[[], datetime] = utc_now
    ) -> None:
        self.database = database
        self.clock = clock

    def start(self, campaign_ids: Sequence[str]) -> DiscoveryRun:
        started_at = self.clock()
        with self.database:
            cursor = self.database.execute(
                "INSERT INTO runs (started_at, campaign_ids) VALUES (?, ?)",
                (started_at.isoformat(), json.dumps(list(campaign_ids))),
            )
        return DiscoveryRun(cursor.lastrowid or 0, started_at, None, tuple(campaign_ids), 0)

    def record(self, run_id: int, report: SourceReport) -> None:
        with self.database:
            self.database.execute(
                "INSERT INTO run_sources (run_id, source, fetched, new_jobs, taken, error) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    report.source,
                    report.fetched,
                    report.new_jobs,
                    json.dumps(report.taken),
                    report.error,
                ),
            )

    def finish(self, run_id: int, linked_jobs: int) -> None:
        with self.database:
            self.database.execute(
                "UPDATE runs SET ended_at = ?, linked_jobs = ? WHERE id = ?",
                (self.clock().isoformat(), linked_jobs, run_id),
            )

    def latest(self, limit: int) -> list[DiscoveryRun]:
        """The last `limit` runs, newest first."""
        rows = self.database.execute(
            "SELECT id, started_at, ended_at, campaign_ids, linked_jobs FROM runs "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return [decoded(row) for row in rows]

    def reports(self, run_id: int) -> list[SourceReport]:
        """The run's sources, in the order they were read."""
        rows = self.database.execute(
            "SELECT source, fetched, new_jobs, taken, error FROM run_sources "
            "WHERE run_id = ? ORDER BY id",
            (run_id,),
        )
        return [
            SourceReport(source, fetched, new_jobs, json.loads(taken), error)
            for source, fetched, new_jobs, taken, error in rows
        ]


def decoded(row: tuple[int, str, str | None, str, int]) -> DiscoveryRun:
    run_id, started_at, ended_at, campaign_ids, linked_jobs = row
    return DiscoveryRun(
        run_id=run_id,
        started_at=datetime.fromisoformat(started_at),
        ended_at=datetime.fromisoformat(ended_at) if ended_at else None,
        campaign_ids=tuple(json.loads(campaign_ids)),
        linked_jobs=linked_jobs,
    )
