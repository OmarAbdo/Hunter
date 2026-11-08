"""The web searches Hunter made, every one with its outcome, so it can be told how often each search
engine answers and how often it asks for a captcha instead. The log also keeps the searches' pace
across runs: the last search and each engine's searches today are read from it."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

Outcome = Literal["links", "nothing", "captcha", "failed"]


@dataclass(frozen=True)
class Searched:
    engine: str
    query: str
    outcome: Outcome
    links: int  # how many result links the search found
    when: datetime


class SearchLog:
    def __init__(self, database: sqlite3.Connection) -> None:
        self.database = database

    def record(self, search: Searched) -> None:
        with self.database:
            self.database.execute(
                "INSERT INTO searches (engine, query, outcome, links, at) VALUES (?, ?, ?, ?, ?)",
                (search.engine, search.query, search.outcome, search.links, stamp(search.when)),
            )

    def summary(self, since: datetime) -> dict[str, dict[str, int]]:
        """Per engine, how many searches since `since` ended in each outcome."""
        rows = self.database.execute(
            "SELECT engine, outcome, count(*) FROM searches WHERE at >= ? "
            "GROUP BY engine, outcome ORDER BY min(id)",
            (stamp(since),),
        )
        counts: dict[str, dict[str, int]] = {}
        for engine, outcome, count in rows:
            counts.setdefault(engine, {})[outcome] = count
        return counts

    def count(self, engine: str, since: datetime) -> int:
        query = "SELECT count(*) FROM searches WHERE engine = ? AND at >= ?"
        return int(self.database.execute(query, (engine, stamp(since))).fetchone()[0])

    def searched(self, query: str, since: datetime) -> bool:
        """Whether this very query got an answer since `since`, from any engine: links, or none.
        A captcha or a failure isn't an answer."""
        found = (
            "SELECT 1 FROM searches WHERE query = ? AND at >= ? "
            "AND outcome IN ('links', 'nothing') LIMIT 1"
        )
        return self.database.execute(found, (query, stamp(since))).fetchone() is not None

    def last(self) -> datetime | None:
        """When the latest search was made, by any engine."""
        (latest,) = self.database.execute("SELECT max(at) FROM searches").fetchone()
        return datetime.fromisoformat(latest) if latest else None


def stamp(moment: datetime) -> str:
    """In UTC, so stamps compare as text."""
    return moment.astimezone(UTC).isoformat()
