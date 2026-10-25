"""Mail marks: per inbox and sender, the IMAP UIDVALIDITY and the last UID Hunter read. Each call
opens its own connection, because the inboxes are read in a thread of their own while discovery
writes to the database from the main one."""

from contextlib import closing
from pathlib import Path

from hunter.adapters.storage.database import open_database


class MailMarks:
    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self, address: str, sender: str) -> tuple[int, int] | None:
        with closing(open_database(self.path)) as database:
            row = database.execute(
                "SELECT validity, last_uid FROM mail_marks WHERE address = ? AND sender = ?",
                (address, sender),
            ).fetchone()
        return (row[0], row[1]) if row else None

    def set(self, address: str, sender: str, validity: int, last_uid: int) -> None:
        with closing(open_database(self.path)) as database, database:
            database.execute(
                "INSERT OR REPLACE INTO mail_marks (address, sender, validity, last_uid) "
                "VALUES (?, ?, ?, ?)",
                (address, sender, validity, last_uid),
            )
