"""StepStone job-alert mails (docs/sources.md): the jobs StepStone's job agent sends to the inbox,
read from the mail's plain text. Hunter never visits stepstone.de for them.

Two layouts are read: "Wir haben 10 neue Job-Matches für dich gefunden", and the older "<Firma> und
N andere Firmen suchen Kandidaten wie Dich". In both, each job is a block of lines: the title (at
times over several lines, often cut short with "..."), the job's link, the company, the place or
places, then facts such as the company's size, the contract, "Vollzeit", "Homeoffice möglich" and
an estimated salary. The older layout follows each job with a snippet and a second link.

What the mail can't give: its links are StepStone's click-tracking redirects, encrypted and new in
every mail, with no job id in them, so a job is known by company, title and place. No layout says
when a job was posted."""

import imaplib
import re
from collections.abc import Sequence
from dataclasses import replace

from hunter.adapters.mail.mailbox import Mail
from hunter.adapters.places import places_from_text
from hunter.adapters.sources.indeed_alerts import Inbox
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import Employment, Posting, SourceRef

SOURCE = "stepstone-alert"
SENDER = "info@jobagent.stepstone.de"
COUNTRY = "DE"
BLOCKS = re.compile(r"\n\s*\n")
JOB_LINK = re.compile(r"https://click\.stepstone\.de/\S+")
# Company, place: what a job's block holds after its link, before the facts.
LINES_AFTER_LINK = 2
CUT_SHORT = "..."
SALARY = "€"
HOME_OFFICE = re.compile(r"\bhomeoffice\b", re.IGNORECASE)
# Words in a job's facts, checked in this order: "Werkstudent, Teilzeit" is a student job.
EMPLOYMENT_WORDS = (
    ("praktik", Employment.INTERNSHIP),
    ("werkstudent", Employment.PART_TIME),
    ("vollzeit", Employment.FULL_TIME),
    ("teilzeit", Employment.PART_TIME),
    ("freie mitarbeit", Employment.CONTRACT),
    ("befristet", Employment.TEMPORARY),
)


class StepStoneAlerts:
    """Every inbox's new StepStone alert mails, as one source. Each inbox remembers the mails
    whose jobs were read, so the next run starts after them."""

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
    blocks = (
        [line.strip() for line in block.splitlines() if line.strip()]
        for block in BLOCKS.split(text)
    )
    return [posting for lines in blocks if (posting := posting_from(lines))]


def posting_from(lines: list[str]) -> Posting | None:
    """A job's block, or None for the mail's other blocks: its buttons ("Alle Jobs ansehen") and
    snippets end with their link."""
    link_at = next((index for index, line in enumerate(lines) if JOB_LINK.fullmatch(line)), 0)
    if link_at == 0 or len(lines) <= link_at + LINES_AFTER_LINK:
        return None
    company, place_text, *facts = lines[link_at + 1 :]
    place, *other_places = places_in(place_text, facts)
    posting = Posting(
        title=" ".join(lines[:link_at]),
        company=company,
        location=place,
        other_locations=tuple(other_places),
        source=SourceRef(source=SOURCE, native_id=""),
        employment=employment_in(facts),
        url=lines[link_at],
    )
    return replace(posting, source=SourceRef(source=SOURCE, native_id=posting.fuzzy_key))


def places_in(text: str, facts: list[str]) -> list[Location]:
    """The places a job names, without the last one when the list is cut short ("Frank...").
    "Homeoffice möglich" makes a job hybrid."""
    named = text.rpartition(",")[0] if text.endswith(CUT_SHORT) else text
    hybrid = any(HOME_OFFICE.search(fact) for fact in facts)
    return [
        replace(place, workplace=Workplace.HYBRID) if hybrid and not place.workplace else place
        for place in places_from_text(named, default_country=COUNTRY)
    ]


def employment_in(facts: list[str]) -> Employment | None:
    """The salary line is left out: its estimate is always "geschätzt für Vollzeit"."""
    words = " ".join(fact for fact in facts if SALARY not in fact).lower()
    return next((kind for word, kind in EMPLOYMENT_WORDS if word in words), None)
