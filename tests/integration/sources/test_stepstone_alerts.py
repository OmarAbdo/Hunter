from datetime import UTC, datetime
from pathlib import Path

import pytest

from hunter.adapters.mail.mailbox import Mail
from hunter.adapters.sources.alerts.stepstone import SENDER, StepStoneAlerts, postings_from_alert
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import Employment, SourceRef

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "sources"
JOB_MATCHES = (FIXTURES / "stepstone-alert-a.txt").read_text(encoding="utf-8")
CANDIDATES_LIKE_YOU = (FIXTURES / "stepstone-alert-b.txt").read_text(encoding="utf-8")
RECEIVED = datetime(2026, 10, 27, 2, 55, tzinfo=UTC)
ONSITE_AD = """Application Development Engineer (f/m/x)
https://click.stepstone.de/f/a/link-1~~/account~/token
ZEISS
Ulm
Vollzeit"""


def test_every_job_in_the_job_matches_mail_becomes_a_posting() -> None:
    postings = postings_from_alert(JOB_MATCHES)
    assert [posting.company for posting in postings] == [
        "Schmitt Engineering",
        "BOEHMERT & BOEHMERT Anwaltspartnerschaft mbB - Patentanwälte Rechtsanwälte",
        "Pädagogisches Landesinstitut Rheinland-Pfalz",
    ]
    first = postings[0]
    assert first.title == "Software Engineer (m/w/d)"
    assert first.location == Location(country="DE", city="Erlangen", workplace=Workplace.HYBRID)
    assert first.url == "https://click.stepstone.de/f/a/link-1~~/account~/token"
    assert first.employment is Employment.FULL_TIME
    assert first.posted_at is None


def test_a_job_without_an_id_is_known_by_company_title_and_place() -> None:
    first = postings_from_alert(JOB_MATCHES)[0]
    assert first.source == SourceRef(source="stepstone-alert", native_id=first.fuzzy_key)


def test_a_job_in_two_towns_is_open_in_both() -> None:
    lawyers = postings_from_alert(JOB_MATCHES)[1]
    assert [place.city for place in lawyers.locations] == ["Munich", "Bremen"]


def test_a_title_over_several_lines_is_one_title() -> None:
    institute = postings_from_alert(JOB_MATCHES)[2]
    assert institute.title == "Softwareentwickler/in (m/w/d) (Kennziffer ..."
    assert institute.employment is Employment.PART_TIME


def test_every_job_in_the_older_mail_becomes_a_posting() -> None:
    postings = postings_from_alert(CANDIDATES_LIKE_YOU)
    assert [posting.title for posting in postings] == [
        "Senior Java Software Engineer (w/m/d)",
        "Frontend Entwickler (m/w/d)",
        "Programmierer/in Werkstudent (m/w/d)",
    ]
    first = postings[0]
    assert first.company == "50Hertz Transmission GmbH"
    assert first.location == Location(country="DE", city="Berlin", workplace=Workplace.HYBRID)
    assert first.url == "https://click.stepstone.de/f/a/link-1~~/account~/token"


def test_a_list_of_towns_cut_short_keeps_the_towns_it_names_in_full() -> None:
    frontend = postings_from_alert(CANDIDATES_LIKE_YOU)[1]
    cities = [place.city for place in frontend.locations]
    assert cities == ["Aachen", "Berlin", "Dresden", "Hamburg"]


def test_a_student_job_is_part_time() -> None:
    student = postings_from_alert(CANDIDATES_LIKE_YOU)[2]
    assert student.employment is Employment.PART_TIME
    assert student.location.city == "Potsdam"


def test_a_job_without_home_office_has_no_workplace_given() -> None:
    [zeiss] = postings_from_alert(ONSITE_AD)
    assert zeiss.location == Location(country="DE", city="Ulm")
    assert zeiss.employment is Employment.FULL_TIME


def test_text_without_jobs_gives_none() -> None:
    buttons = "Alle Jobs ansehen\nhttps://click.stepstone.de/f/a/link-4~~/account~/token\n\nNeu"
    assert postings_from_alert(buttons) == []


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
    older = Mail(uid=3, validity=7, received_at=RECEIVED, text=CANDIDATES_LIKE_YOU)
    newer = Mail(uid=4, validity=7, received_at=RECEIVED, text=JOB_MATCHES)
    first, second = StandInMailbox([older, newer]), StandInMailbox([])
    postings = StepStoneAlerts([first, second]).fetch()
    assert len(postings) == 6
    assert first.remembered == [older, newer]


def test_an_inbox_that_cannot_be_read_makes_the_source_unavailable() -> None:
    with pytest.raises(SourceUnavailableError, match="connection refused"):
        StepStoneAlerts([StandInMailbox([], down=True)]).fetch()
    assert StepStoneAlerts([]).name == "stepstone-alert"
