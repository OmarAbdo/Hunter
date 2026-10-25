"""The probe log: which companies have been probed for a board, found or not, so each is probed
once."""

import sqlite3
from datetime import datetime


class ProbeLog:
    def __init__(self, database: sqlite3.Connection) -> None:
        self.database = database

    def record(self, company_key: str, probed_at: datetime) -> None:
        with self.database:
            self.database.execute(
                "INSERT OR REPLACE INTO probes (company_key, probed_at) VALUES (?, ?)",
                (company_key, probed_at.isoformat()),
            )

    def probed(self) -> set[str]:
        return {key for (key,) in self.database.execute("SELECT company_key FROM probes")}
