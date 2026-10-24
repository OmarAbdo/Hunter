"""The pool: every job Hunter has seen, stored once, with a sighting for each source that showed it.

A posting is the same job as one in the pool when the employer's own key matches, or else when
company, title and place match a job that doesn't have a different employer key."""

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from typing import Any

from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.pooled import Pooled
from hunter.domain.discovery.posting import EmployerRef, Employment, Posting, SourceRef


class Pool:
    def __init__(self, database: sqlite3.Connection) -> None:
        self.database = database

    def add(self, posting: Posting, seen_at: datetime) -> Pooled:
        """The job the posting shows, new or already known, with this sighting recorded."""
        with self.database:
            known = self._find(posting)
            if known is None:
                job_id = self._insert(posting, seen_at)
            else:
                job_id = known
                self._learn_employer(job_id, posting)
            self._record_sighting(job_id, posting.source, seen_at)
        return Pooled(job_id=job_id, is_new=known is None)

    def posting(self, job_id: int) -> Posting:
        row = self.database.execute("SELECT posting FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return decoded(row[0])

    def sightings(self, job_id: int) -> list[SourceRef]:
        rows = self.database.execute(
            "SELECT source, native_id FROM sightings WHERE job_id = ? ORDER BY rowid", (job_id,)
        )
        return [SourceRef(source=source, native_id=native_id) for source, native_id in rows]

    def job_count(self) -> int:
        return int(self.database.execute("SELECT count(*) FROM jobs").fetchone()[0])

    def _find(self, posting: Posting) -> int | None:
        row = self.database.execute(
            "SELECT id FROM jobs WHERE exact_key = ? "
            "UNION ALL "
            "SELECT id FROM jobs WHERE fuzzy_key = ? AND (exact_key IS NULL OR ? IS NULL) "
            "LIMIT 1",
            (posting.exact_key, posting.fuzzy_key, posting.exact_key),
        ).fetchone()
        return int(row[0]) if row else None

    def _insert(self, posting: Posting, seen_at: datetime) -> int:
        cursor = self.database.execute(
            "INSERT INTO jobs (exact_key, fuzzy_key, posting, first_seen) VALUES (?, ?, ?, ?)",
            (posting.exact_key, posting.fuzzy_key, encoded(posting), seen_at.isoformat()),
        )
        return int(cursor.lastrowid or 0)

    def _learn_employer(self, job_id: int, posting: Posting) -> None:
        """A job first seen on a job board takes the employer's own posting once it shows up."""
        if posting.exact_key:
            self.database.execute(
                "UPDATE jobs SET exact_key = ?, posting = ? WHERE id = ? AND exact_key IS NULL",
                (posting.exact_key, encoded(posting), job_id),
            )

    def _record_sighting(self, job_id: int, source: SourceRef, seen_at: datetime) -> None:
        self.database.execute(
            "INSERT INTO sightings (job_id, source, native_id, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (source, native_id) DO UPDATE SET last_seen = excluded.last_seen",
            (job_id, source.source, source.native_id, seen_at.isoformat(), seen_at.isoformat()),
        )


def plain(value: object) -> object:
    """What JSON can't hold itself: enums, sets and times."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, frozenset):
        return sorted(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Can't store {value!r}")


def encoded(posting: Posting) -> str:
    return json.dumps(asdict(posting), default=plain, ensure_ascii=False)


def decoded_location(place: dict[str, Any]) -> Location:
    return Location(
        country=place["country"],
        city=place["city"],
        workplace=Workplace(place["workplace"]) if place["workplace"] else None,
        remote_scope=frozenset(place["remote_scope"]),
    )


def decoded(text: str) -> Posting:
    record = json.loads(text)
    employer = record["employer"]
    return Posting(
        title=record["title"],
        company=record["company"],
        location=decoded_location(record["location"]),
        other_locations=tuple(map(decoded_location, record.get("other_locations", []))),
        source=SourceRef(**record["source"]),
        employer=EmployerRef(**employer) if employer else None,
        employment=Employment(record["employment"]) if record["employment"] else None,
        url=record["url"],
        apply_url=record["apply_url"],
        description=record["description"],
        posted_at=datetime.fromisoformat(record["posted_at"]) if record["posted_at"] else None,
    )
