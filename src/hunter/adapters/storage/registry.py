"""The company registry: every company Hunter knows, with its boards and their feed status."""

import json
import sqlite3

from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.company import Company, FeedStatus

SELECT = (
    "SELECT name, feeds, website FROM companies "
    "LEFT JOIN websites ON websites.company_key = companies.key"
)


class Registry:
    def __init__(self, database: sqlite3.Connection) -> None:
        self.database = database

    def save(self, company: Company) -> None:
        """Stores the company as it is now, replacing what was stored under its key."""
        with self.database:
            self.database.execute(
                "INSERT INTO companies (key, name, feeds) VALUES (?, ?, ?) "
                "ON CONFLICT (key) DO UPDATE SET name = excluded.name, feeds = excluded.feeds",
                (company.key, company.name, encoded_feeds(company)),
            )
            if company.website:
                self.database.execute(
                    "INSERT OR REPLACE INTO websites (company_key, website) VALUES (?, ?)",
                    (company.key, company.website),
                )
            self.database.executemany(
                "INSERT OR REPLACE INTO boards (board, company_key) VALUES (?, ?)",
                [(board.key, company.key) for board in company.boards],
            )

    def get(self, key: str) -> Company | None:
        row = self.database.execute(f"{SELECT} WHERE key = ?", (key,)).fetchone()
        return decoded(*row) if row else None

    def owner_of(self, board: Board) -> Company | None:
        row = self.database.execute(
            "SELECT company_key FROM boards WHERE board = ?", (board.key,)
        ).fetchone()
        return self.get(row[0]) if row else None

    def all(self) -> list[Company]:
        rows = self.database.execute(f"{SELECT} ORDER BY name")
        return [decoded(*row) for row in rows]


def encoded_feeds(company: Company) -> str:
    return json.dumps(
        [
            {"ats": board.ats, "slug": board.slug, "status": status.value}
            for board, status in company.feeds.items()
        ]
    )


def decoded(name: str, feeds: str, website: str | None) -> Company:
    return Company(
        name=name,
        website=website,
        feeds={
            Board(ats=feed["ats"], slug=feed["slug"]): FeedStatus(feed["status"])
            for feed in json.loads(feeds)
        },
    )
