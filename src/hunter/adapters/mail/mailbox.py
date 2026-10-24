"""The inboxes (docs/sources.md), read over IMAP with the app passwords in var/accounts.toml.
Hunter only reads: the inbox is opened read-only, and nothing is flagged, moved or deleted. A mark
per inbox and sender remembers the last mail read, so each mail is read once."""

import imaplib
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from typing import Any

from hunter.adapters.config.credentials import MailAccount
from hunter.adapters.text.html_text import plain_text

TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class Mail:
    """One mail. `validity` is the inbox's IMAP UIDVALIDITY: UIDs only count within it."""

    uid: int
    validity: int
    received_at: datetime
    text: str


class MailMarks:
    """Per inbox and sender: the UIDVALIDITY and the last UID read."""

    def __init__(self, database: sqlite3.Connection) -> None:
        self.database = database

    def get(self, address: str, sender: str) -> tuple[int, int] | None:
        row = self.database.execute(
            "SELECT validity, last_uid FROM mail_marks WHERE address = ? AND sender = ?",
            (address, sender),
        ).fetchone()
        return (row[0], row[1]) if row else None

    def set(self, address: str, sender: str, validity: int, last_uid: int) -> None:
        with self.database:
            self.database.execute(
                "INSERT OR REPLACE INTO mail_marks (address, sender, validity, last_uid) "
                "VALUES (?, ?, ?, ?)",
                (address, sender, validity, last_uid),
            )


class Mailbox:
    def __init__(
        self,
        account: MailAccount,
        marks: MailMarks,
        connect: Callable[..., Any] = imaplib.IMAP4_SSL,
    ) -> None:
        self.account = account
        self.marks = marks
        self.connect = connect

    def new_mails(self, sender: str) -> list[Mail]:
        """The mails from `sender` that arrived after the last one remembered."""
        connection = self.connect(self.account.host, timeout=TIMEOUT_SECONDS)
        try:
            connection.login(self.account.address, self.account.app_password)
            connection.select("INBOX", readonly=True)
            validity = int(connection.response("UIDVALIDITY")[1][0])
            first = self._first_unread(sender, validity)
            found = connection.uid("SEARCH", "FROM", f'"{sender}"', "UID", f"{first}:*")[1]
            uids = [int(uid) for uid in found[0].split() if int(uid) >= first]
            return [read_mail(connection, uid, validity) for uid in uids]
        finally:
            connection.logout()

    def remember(self, sender: str, mails: Sequence[Mail]) -> None:
        """Marks these mails as read by Hunter, so the next call starts after them."""
        if mails:
            last = max(mails, key=lambda mail: mail.uid)
            self.marks.set(self.account.address, sender, last.validity, last.uid)

    def _first_unread(self, sender: str, validity: int) -> int:
        """IMAP UIDs only count within one UIDVALIDITY; a rebuilt inbox is read from the start."""
        mark = self.marks.get(self.account.address, sender)
        return mark[1] + 1 if mark and mark[0] == validity else 1


def read_mail(connection: Any, uid: int, validity: int) -> Mail:
    raw = connection.uid("FETCH", str(uid), "(RFC822)")[1][0][1]
    message = BytesParser(policy=policy.default).parsebytes(raw)
    return Mail(uid, validity, parsedate_to_datetime(message["Date"]), text_of(message))


def text_of(message: EmailMessage) -> str:
    """The mail's plain text, or its HTML as plain text when it has no plain part."""
    body = message.get_body(preferencelist=("plain", "html"))
    if body is None:
        return ""
    content = str(body.get_content())
    return content if body.get_content_type() == "text/plain" else plain_text(content)
