"""LinkedIn job-alert mails (docs/sources.md): the jobs LinkedIn sends to the inbox for a saved
search, read from the mail's plain text. Hunter never visits linkedin.com for them and never
requests a link in the mail, not even to resolve it: those links can log in as their reader. Only
the job's id is taken from them, and the job's page is built from that id, offline.

Each job in the mail is a block closed by a rule of dashes: the title, the company, the place, then
at times "Apply with resume & profile" (LinkedIn's Easy Apply), a line about the company or the
reader's ties to it, and "View job: " with its link. The first block starts with the alert's own
lines. The same sender's other mails ("Do you still want job alerts ...") have no job link, so they
give no jobs.

What the plain text can't give: the salary, and the workplace the mail's HTML shows after the place
("Berlin (Hybrid)"), so a workplace is only read where the plain text has one. Neither part says
when a job was posted. And a mail shows only its first few jobs: the rest of its "30+ new jobs" are
behind "See all jobs", which Hunter doesn't follow."""

import imaplib
import re
from collections.abc import Sequence
from dataclasses import replace

from hunter.adapters.mail.mailbox import Mail
from hunter.adapters.places import places_from_text
from hunter.adapters.sources.indeed_alerts import Inbox
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import Posting, SourceRef

SOURCE = "linkedin-alert"
SENDER = "jobalerts-noreply@linkedin.com"
JOB_PAGE = "https://www.linkedin.com/jobs/view/{job_id}/"
RULE = re.compile(r"^-{20,}[ \t\r]*$", re.MULTILINE)
JOB_LINK = re.compile(
    r"^.*https://[a-z]+\.linkedin\.com/\S*?(?:jobs/view/|[?&]currentJobId=)(?P<job_id>\d+)",
    re.MULTILINE,
)
# The alert's own lines, above the first job: "Your job alert for ...", "30+ new jobs match ...".
ALERT_LINE = re.compile(r"^(?:your job alert for\b|\d+\+? new jobs?\b)", re.IGNORECASE)
QUICK_APPLY = re.compile(r"^(?:apply with resume\b|easy apply\b)", re.IGNORECASE)
ON_SITE = re.compile(r"\s*\(?\bon-?site\b\)?", re.IGNORECASE)
JOB_LINES = ("title", "company", "place")


class LinkedInAlerts:
    """Every inbox's new LinkedIn alert mails, as one source. Each inbox remembers the mails whose
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
    return [posting for block in RULE.split(text) if (posting := posting_from(block))]


def posting_from(block: str) -> Posting | None:
    """A job's block, or None for the mail's other blocks: they have no job link, or nothing above
    it. Lines after the place are facts, whatever they say, so a new one can't shift the job."""
    link = JOB_LINK.search(block)
    if link is None:
        return None
    lines = [line.strip() for line in block[: link.start()].splitlines() if line.strip()]
    job = [line for line in lines if not ALERT_LINE.match(line)]
    if len(job) < len(JOB_LINES):
        return None
    title, company, place_text, *facts = job
    place, *other_places = places_in(place_text)
    return Posting(
        title=title,
        company=company,
        location=place,
        other_locations=tuple(other_places),
        source=SourceRef(source=SOURCE, native_id=link["job_id"]),
        url=JOB_PAGE.format(job_id=link["job_id"]),
        quick_apply=any(QUICK_APPLY.match(fact) for fact in facts),
    )


def places_in(text: str) -> list[Location]:
    """The places a job names. Remote and hybrid are read with the place, "On-site" here."""
    workplace = Workplace.ONSITE if ON_SITE.search(text) else None
    return [
        replace(place, workplace=workplace or place.workplace)
        for place in places_from_text(ON_SITE.sub("", text))
    ]
