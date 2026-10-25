"""The pool as resolving sees it: jobs without the employer's key, the jobs on a company's boards,
and merging one job into another."""

import sqlite3

from hunter.adapters.storage.pool import decoded
from hunter.domain.discovery.posting import Posting


class JobLinks:
    def __init__(self, database: sqlite3.Connection) -> None:
        self.database = database

    def unresolved(self) -> list[tuple[int, Posting]]:
        rows = self.database.execute("SELECT id, posting FROM jobs WHERE exact_key IS NULL")
        return [(int(job_id), decoded(posting)) for job_id, posting in rows]

    def employer_jobs(self, company_key: str) -> list[tuple[int, Posting]]:
        """An employer key is `ats:board:job-id`, a board key `ats:board`."""
        rows = self.database.execute(
            "SELECT jobs.id, jobs.posting FROM jobs JOIN boards "
            "ON substr(jobs.exact_key, 1, length(boards.board) + 1) = boards.board || ':' "
            "WHERE boards.company_key = ? ORDER BY jobs.id",
            (company_key,),
        )
        return [(int(job_id), decoded(posting)) for job_id, posting in rows]

    def merge(self, job_id: int, into: int) -> None:
        """The job's sightings move to `into`; its campaign verdicts go, `into` has its own."""
        with self.database:
            self.database.execute(
                "UPDATE sightings SET job_id = ? WHERE job_id = ?", (into, job_id)
            )
            self.database.execute("DELETE FROM matches WHERE job_id = ?", (job_id,))
            self.database.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
