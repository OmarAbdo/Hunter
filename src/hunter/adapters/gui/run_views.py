"""What the GUI shows of discovery runs, as plain JSON-ready values: the latest runs with what each
source brought, and the sites holding Hunter off."""

import sqlite3
from collections.abc import Callable
from datetime import datetime
from typing import Any

from hunter.adapters.storage.holds import Holds
from hunter.adapters.storage.run_log import RunLog, utc_now
from hunter.application.discover import SourceReport


def runs_view(database: sqlite3.Connection, limit: int = 10) -> list[Any]:
    """The latest discovery runs, the newest first, each with what its sources brought."""
    runs = RunLog(database)
    shown = []
    for run in runs.latest(limit):
        reports = runs.reports(run.run_id)
        shown.append(
            {
                "id": run.run_id,
                "started_at": run.started_at.isoformat(),
                "ended_at": run.ended_at.isoformat() if run.ended_at else None,
                "linked": run.linked_jobs,
                "fetched": sum(report.fetched for report in reports),
                "new": sum(report.new_jobs for report in reports),
                "taken": sum(sum(report.taken.values()) for report in reports),
                "failed": sum(1 for report in reports if report.error),
                "sources": [source_of(report) for report in reports],
            }
        )
    return shown


def source_of(report: SourceReport) -> dict[str, Any]:
    return {
        "source": report.source,
        "fetched": report.fetched,
        "new": report.new_jobs,
        "taken": sum(report.taken.values()),
        "error": report.error,
    }


def held_view(
    database: sqlite3.Connection, clock: Callable[[], datetime] = utc_now
) -> list[dict[str, str]]:
    """The sites that asked Hunter for a pause that hasn't ended, the soonest to end first."""
    held = sorted(Holds(database).current(clock()).items(), key=lambda pause: pause[1])
    return [{"host": host, "until": until.isoformat()} for host, until in held]
