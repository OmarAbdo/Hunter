"""The mailbox against a stand-in IMAP server that keeps real mail messages. Gmail itself can't run
in a test; the messages and the IMAP answers have their real shapes."""

import threading
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

from hunter.adapters.credentials import MailAccount, accounts_from
from hunter.adapters.mail.mailbox import Mailbox
from hunter.adapters.storage.mail_marks import MailMarks

ACCOUNT = MailAccount(address="jobs@example.com", app_password="secret", host="imap.example.com")
INDEED = "donotreply@jobalert.indeed.com"
RECEIVED = datetime(2026, 10, 24, 9, 0, tzinfo=UTC)


def message(sender: str, text: str, html: str | None = None) -> bytes:
    mail = EmailMessage()
    mail["From"] = sender
    mail["Subject"] = "Jobs"
    mail["Date"] = "Sat, 24 Oct 2026 09:00:00 +0000"
    mail.set_content(text)
    if html:
        mail.add_alternative(html, subtype="html")
    return bytes(mail)


class StandInImap:
    """Answers the IMAP commands the mailbox sends, from `messages` keyed by UID."""

    def __init__(self, messages: dict[int, bytes], validity: int = 7) -> None:
        self.messages = messages
        self.validity = validity
        self.logged_in_as = ""

    def login(self, user: str, password: str) -> tuple[str, list[bytes]]:
        if password == ACCOUNT.app_password:
            self.logged_in_as = user
        return "OK", [b"logged in"]

    def select(self, mailbox: str, readonly: bool) -> tuple[str, list[bytes]]:
        return "OK", [str(len(self.messages)).encode()]

    def response(self, code: str) -> tuple[str, list[bytes]]:
        return code, [str(self.validity).encode()]

    def uid(self, command: str, *args: str) -> tuple[str, list[object]]:
        if command == "SEARCH":
            first, sender = int(args[-1].split(":")[0]), args[1].strip('"')
            found = [
                uid for uid, raw in self.messages.items() if uid >= first and sender.encode() in raw
            ]
            return "OK", [" ".join(map(str, found)).encode()]
        return "OK", [(b"1 (RFC822)", self.messages[int(args[0])])]

    def logout(self) -> tuple[str, list[bytes]]:
        return "BYE", [b""]


def mailbox(tmp_path: Path, server: StandInImap) -> Mailbox:
    marks = MailMarks(tmp_path / "hunter.db")
    return Mailbox(ACCOUNT, marks, connect=lambda host, timeout: server)


def test_new_mails_from_a_sender_with_their_text_and_time(tmp_path: Path) -> None:
    server = StandInImap({3: message(INDEED, "Backend Engineer"), 4: message("friend@x.com", "Hi")})
    [mail] = mailbox(tmp_path, server).new_mails(INDEED)
    assert (mail.uid, mail.text.strip(), mail.received_at) == (3, "Backend Engineer", RECEIVED)
    assert server.logged_in_as == ACCOUNT.address


def test_a_mail_is_read_once_after_it_is_remembered(tmp_path: Path) -> None:
    server = StandInImap({3: message(INDEED, "first")})
    box = mailbox(tmp_path, server)
    box.remember(INDEED, box.new_mails(INDEED))
    server.messages[5] = message(INDEED, "second")
    assert [mail.uid for mail in box.new_mails(INDEED)] == [5]


def test_marks_can_be_kept_from_another_thread(tmp_path: Path) -> None:
    server = StandInImap({3: message(INDEED, "first")})
    box = mailbox(tmp_path, server)
    worker = threading.Thread(target=lambda: box.remember(INDEED, box.new_mails(INDEED)))
    worker.start()
    worker.join()
    assert box.new_mails(INDEED) == []


def test_marks_survive_a_restart(tmp_path: Path) -> None:
    server = StandInImap({3: message(INDEED, "first")})
    first = mailbox(tmp_path, server)
    first.remember(INDEED, first.new_mails(INDEED))
    assert mailbox(tmp_path, server).new_mails(INDEED) == []


def test_a_rebuilt_inbox_is_read_from_the_start(tmp_path: Path) -> None:
    server = StandInImap({3: message(INDEED, "first")})
    box = mailbox(tmp_path, server)
    box.remember(INDEED, box.new_mails(INDEED))
    server.validity = 8
    assert [mail.uid for mail in box.new_mails(INDEED)] == [3]


def test_a_mail_with_only_html_is_read_as_plain_text(tmp_path: Path) -> None:
    html_only = EmailMessage()
    html_only["From"], html_only["Date"] = INDEED, "Sat, 24 Oct 2026 09:00:00 +0000"
    html_only.set_content("<p>Backend <b>Engineer</b></p>", subtype="html")
    [mail] = mailbox(tmp_path, StandInImap({1: bytes(html_only)})).new_mails(INDEED)
    assert mail.text == "Backend Engineer"


def test_accounts_come_from_the_credentials_file(tmp_path: Path) -> None:
    (tmp_path / "accounts.toml").write_text(
        '[[mailbox]]\naddress = "jobs@example.com"\napp_password = "secret"\n'
        'host = "imap.example.com"\n',
        encoding="utf-8",
    )
    assert accounts_from(tmp_path / "accounts.toml") == [ACCOUNT]
