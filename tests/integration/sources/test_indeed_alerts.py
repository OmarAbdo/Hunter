from datetime import UTC, datetime, timedelta
from pathlib import Path

from hunter.adapters.sources.indeed_alerts import postings_from_alert
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import SourceRef

ALERT = (
    Path(__file__).resolve().parents[2] / "fixtures" / "sources" / "indeed-alert.txt"
).read_text(encoding="utf-8")
RECEIVED = datetime(2026, 10, 24, 9, 0, tzinfo=UTC)
AD = """Software Engineer Golang (m/w/d)
Hays Professional Solutions GmbH - Erlangen
Schnellbewerbung
Entwicklung industrieller Monitoring-Softwarelösungen im Backend und Frontend.
Vor 4 Tagen
https://de.indeed.com/pagead/clk/dl"""


def test_every_job_in_the_alert_becomes_a_posting() -> None:
    postings = postings_from_alert(ALERT, RECEIVED)
    assert len(postings) == 8
    first = postings[0]
    assert (first.title, first.company) == ("Tech Lead - Craftnote", "Aceve")
    assert first.location == Location(country="DE", city="Berlin")
    assert first.source == SourceRef(source="indeed-alert", native_id="2fa08af05d11b93b")
    assert first.url == "https://de.indeed.com/viewjob?jk=2fa08af05d11b93b"
    assert first.description.startswith("You")


def test_company_names_with_dashes_keep_them() -> None:
    php = postings_from_alert(ALERT, RECEIVED)[3]
    assert (php.company, php.location.city) == ("Bartko & Reher GmbH & Co. KG", "Berlin")


def test_quick_apply_is_marked() -> None:
    postings = postings_from_alert(ALERT, RECEIVED)
    assert postings[0].quick_apply
    assert not postings[4].quick_apply


def test_the_age_gives_the_posting_time() -> None:
    postings = postings_from_alert(ALERT, RECEIVED)
    assert postings[0].posted_at == RECEIVED - timedelta(days=1)
    assert postings[1].posted_at == RECEIVED - timedelta(days=7)
    assert postings[5].posted_at == RECEIVED


def test_salary_and_employer_badges_stay_out_of_the_description() -> None:
    founding = postings_from_alert(ALERT, RECEIVED)[2]
    assert founding.description.startswith("Infinos ist")


def test_a_sponsored_job_without_a_job_key_is_still_read() -> None:
    [sponsored] = postings_from_alert(AD, RECEIVED)
    assert (sponsored.company, sponsored.location.city) == (
        "Hays Professional Solutions GmbH",
        "Erlangen",
    )
    assert sponsored.source.native_id == sponsored.fuzzy_key
    assert sponsored.url is None


def test_home_office_jobs_are_remote_in_the_alerts_country() -> None:
    home = AD.replace("- Erlangen", "- Home Office")
    [remote] = postings_from_alert(home, RECEIVED)
    assert remote.location == Location(country="DE", workplace=Workplace.REMOTE)


def test_text_without_jobs_gives_none() -> None:
    assert postings_from_alert("Indeed Job Alert\n\nNothing new today.", RECEIVED) == []
