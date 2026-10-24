"""Campaign matches: for each job a campaign has looked at, whether it took the job or why not."""

import sqlite3
from datetime import datetime

from hunter.domain.discovery.campaign import Rejection


class Matches:
    def __init__(self, database: sqlite3.Connection) -> None:
        self.database = database

    def record(
        self, job_id: int, campaign_id: str, rejection: Rejection | None, decided_at: datetime
    ) -> None:
        """Stores the campaign's verdict on the job; None means the campaign took it."""
        with self.database:
            self.database.execute(
                "INSERT OR REPLACE INTO matches (job_id, campaign_id, rejection, decided_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    job_id,
                    campaign_id,
                    rejection.value if rejection else None,
                    decided_at.isoformat(),
                ),
            )

    def decided(self, job_id: int, campaign_id: str) -> bool:
        row = self.database.execute(
            "SELECT 1 FROM matches WHERE job_id = ? AND campaign_id = ?", (job_id, campaign_id)
        ).fetchone()
        return row is not None

    def matched(self, campaign_id: str) -> list[int]:
        rows = self.database.execute(
            "SELECT job_id FROM matches "
            "WHERE campaign_id = ? AND rejection IS NULL ORDER BY job_id",
            (campaign_id,),
        )
        return [job_id for (job_id,) in rows]

    def rejections(self, campaign_id: str) -> dict[Rejection, int]:
        rows = self.database.execute(
            "SELECT rejection, count(*) FROM matches "
            "WHERE campaign_id = ? AND rejection IS NOT NULL GROUP BY rejection",
            (campaign_id,),
        )
        return {Rejection(rejection): count for rejection, count in rows}
