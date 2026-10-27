from datetime import UTC, datetime
from pathlib import Path

import pytest

from hunter.adapters.mail.mailbox import Mail
from hunter.adapters.sources.alerts.xing import SENDER, XingAlerts, postings_from_alert
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import Employment, SourceRef

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "sources"
ALERT_A = (FIXTURES / "xing-alert-a.txt").read_text(encoding="utf-8")
ALERT_B = (FIXTURES / "xing-alert-b.txt").read_text(encoding="utf-8")
RECEIVED = datetime(2026, 10, 27, 7, 21, tzinfo=UTC)
FREELANCE = """----------------------------------------

Be an early applicant
UX Backend Developer
=> https://www.xing.com/m/the-link-7

Cegeka Deutschland GmbH
Remote


Self-employed

----------------------------------------"""


def test_every_job_in_the_alert_becomes_a_posting() -> None:
    postings = postings_from_alert(ALERT_A)
    assert len(postings) == 3
    first = postings[0]
    assert first.title == "Backend Entwickler - Künstliche Intelligenz / RAG (m/w/d)"
    assert first.company == "Workwise GmbH"
    assert first.location == Location(country="DE", city="Hamburg")
    assert first.url == "https://www.xing.com/m/the-link-1"
    assert first.employment is Employment.FULL_TIME
    assert first.posted_at is None


def test_a_job_is_known_by_company_title_and_place() -> None:
    """XING's links are per mail and reader, and carry no job id: a job has none to keep."""
    second = postings_from_alert(ALERT_A)[1]
    assert second.source == SourceRef(source="xing-alert", native_id=second.fuzzy_key)
    assert second.location.city == "Munich"
    assert second.employment is Employment.PART_TIME


def test_the_easy_apply_after_a_job_marks_it() -> None:
    marked = [posting.quick_apply for posting in postings_from_alert(ALERT_A)]
    assert marked == [True, False, False]
    assert [posting.quick_apply for posting in postings_from_alert(ALERT_B)] == [False, False, True]


def test_the_startup_label_is_no_part_of_the_title() -> None:
    startup = postings_from_alert(ALERT_A)[2]
    assert (startup.title, startup.company) == ("Backend-Development", "Stackmeister")


def test_html_entities_in_the_text_are_read() -> None:
    first = postings_from_alert(ALERT_B)[0]
    assert first.title == "AI Engineer (m/w/d) – Softwareentwicklung & Agentic AI"
    assert first.location == Location(country="DE", city="Ulm")


def test_small_towns_keep_germany() -> None:
    airbus, c_intact = postings_from_alert(ALERT_B)[1:]
    assert (airbus.company, airbus.location) == ("Airbus", Location(country="DE"))
    assert c_intact.title.startswith("IT Consultant")


def test_freelance_and_remote_jobs() -> None:
    [freelance] = postings_from_alert(FREELANCE)
    assert freelance.employment is Employment.CONTRACT
    assert freelance.location == Location(country="DE", workplace=Workplace.REMOTE)


def test_text_without_jobs_gives_none() -> None:
    assert postings_from_alert("XING\n\nNothing new today.") == []


class StandInMailbox:
    def __init__(self, mails: list[Mail], *, down: bool = False) -> None:
        self.mails = mails
        self.down = down
        self.remembered: list[Mail] = []

    def new_mails(self, sender: str) -> list[Mail]:
        if self.down:
            raise OSError("imap.gmail.com: connection refused")
        return self.mails if sender == SENDER else []

    def remember(self, sender: str, mails: list[Mail]) -> None:
        self.remembered = mails


def test_the_alert_source_reads_every_inbox_and_remembers_what_it_read() -> None:
    first = Mail(uid=3, validity=7, received_at=RECEIVED, text=ALERT_A)
    second = Mail(uid=4, validity=7, received_at=RECEIVED, text=ALERT_B)
    one, other = StandInMailbox([first, second]), StandInMailbox([])
    postings = XingAlerts([one, other]).fetch()
    assert len(postings) == 6
    assert one.remembered == [first, second]


def test_an_inbox_that_cannot_be_read_makes_the_source_unavailable() -> None:
    with pytest.raises(SourceUnavailableError, match="connection refused"):
        XingAlerts([StandInMailbox([], down=True)]).fetch()
    assert XingAlerts([]).name == "xing-alert"
