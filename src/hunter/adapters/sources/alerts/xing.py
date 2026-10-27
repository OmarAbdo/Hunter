"""XING job-alert mails (docs/sources.md): the jobs XING sends to the inbox for a search alert,
read from the mail's plain text. Hunter never visits xing.com for them.

Each job in the mail is a block between two rules of dashes: an optional badge ("Urgently
hiring"), the title, "=> " and the job's link, the company, the place, and the employment type
run together with the salary ("Full-time50,500 € - 66,000 €"). An "Easy apply" box after a block
marks that job. A place too small to be known keeps Germany, XING's home.

The mail gives no posting date and no XING job id: its links are short links made for one mail
and its reader, with nothing of the job in them. So a job is known by company, title and place,
and its link is the mail's link, which leads to the job's page on XING."""

import html
import imaplib
import re
from collections.abc import Sequence
from dataclasses import replace
from typing import Protocol

from hunter.adapters.mail.mailbox import Mail
from hunter.adapters.places import places_from_text
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.posting import Employment, Posting, SourceRef

SOURCE = "xing-alert"
SENDER = "jobs@mail.xing.com"
RULE = re.compile(r"^-{40}[ \t\r]*$", re.MULTILINE)
JOB_LINK = re.compile(r"=> https://www\.xing\.com/m/\S+")
EASY_APPLY = "Easy apply:"
# XING's label on jobs it takes from startup job boards; it isn't part of the job's title.
STARTUP_LABEL = re.compile(r"^Startup Job / Mitgründer / Praktika:\s*")
EMPLOYMENTS = {
    "full-time": Employment.FULL_TIME,
    "part-time": Employment.PART_TIME,
    "self-employed": Employment.CONTRACT,
}
EMPLOYMENT = re.compile(r"^(?P<kind>" + "|".join(EMPLOYMENTS) + ")", re.IGNORECASE)
HOME_COUNTRY = "DE"


class Inbox(Protocol):
    def new_mails(self, sender: str) -> list[Mail]: ...

    def remember(self, sender: str, mails: list[Mail]) -> None: ...


class XingAlerts:
    """Every inbox's new XING alert mails, as one source. Each inbox remembers the mails whose
    jobs were read, so the next run starts after them."""

    name = SOURCE

    def __init__(self, inboxes: Sequence[Inbox]) -> None:
        self.inboxes = inboxes

    def fetch(self) -> list[Posting]:
        postings: list[Posting] = []
        for inbox in self.inboxes:
            mails = self._new_mails(inbox)
            for mail in mails:
                postings += postings_from_alert(mail.text)
            inbox.remember(SENDER, mails)
        return postings

    def _new_mails(self, inbox: Inbox) -> list[Mail]:
        try:
            return inbox.new_mails(SENDER)
        except (OSError, imaplib.IMAP4.error) as error:
            raise SourceUnavailableError(f"{self.name}: {error}") from error


def postings_from_alert(text: str) -> list[Posting]:
    """The plain text keeps the HTML's entities ("&amp;"), so each line is unescaped."""
    postings: list[Posting] = []
    for block in RULE.split(text):
        lines = [html.unescape(line.strip()) for line in block.splitlines() if line.strip()]
        if EASY_APPLY in lines and postings:
            postings[-1] = replace(postings[-1], quick_apply=True)
        elif posting := posting_from(lines):
            postings.append(posting)
    return postings


def posting_from(lines: list[str]) -> Posting | None:
    """A job's block: the title, its link, then the company and the place at least."""
    link = next((index for index, line in enumerate(lines) if JOB_LINK.fullmatch(line)), 0)
    details = lines[link + 1 :]
    if link == 0 or len(details) < len(("company", "place")):
        return None
    place, *other_places = places_from_text(details[1], default_country=HOME_COUNTRY)
    posting = Posting(
        title=STARTUP_LABEL.sub("", lines[link - 1]),
        company=details[0],
        location=place,
        other_locations=tuple(other_places),
        source=SourceRef(source=SOURCE, native_id=""),
        employment=employment_in(details[2:]),
        url=lines[link].removeprefix("=> "),
    )
    return replace(posting, source=SourceRef(source=SOURCE, native_id=posting.fuzzy_key))


def employment_in(lines: list[str]) -> Employment | None:
    kinds = (kind for line in lines if (kind := EMPLOYMENT.match(line)))
    kind = next(kinds, None)
    return EMPLOYMENTS[kind["kind"].lower()] if kind else None
