from dataclasses import replace

from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import EmployerRef, Employment, Posting, SourceRef

ALERT = Posting(
    title="Senior Backend Engineer (m/w/d)",
    company="Nextcloud GmbH",
    location=Location(country="DE", city="Berlin", workplace=Workplace.HYBRID),
    source=SourceRef(source="indeed-alert", native_id="c7ce5aa8dcb2f774"),
)


def test_the_exact_key_comes_from_the_employers_own_system() -> None:
    employer = EmployerRef(ats="greenhouse", board="nextcloud", job_id="4711")
    assert replace(ALERT, employer=employer).exact_key == "greenhouse:nextcloud:4711"


def test_without_the_employers_system_there_is_no_exact_key() -> None:
    assert ALERT.exact_key is None


def test_the_fuzzy_key_is_company_title_and_place() -> None:
    assert ALERT.fuzzy_key == "nextcloud|senior backend engineer|DE:berlin"


def test_the_same_job_from_two_sources_has_one_fuzzy_key() -> None:
    elsewhere = replace(
        ALERT,
        title="Senior Backend Engineer (all genders)",
        company="Nextcloud",
        source=SourceRef(source="greenhouse", native_id="4711"),
    )
    assert elsewhere.fuzzy_key == ALERT.fuzzy_key


def test_a_place_without_a_city_keys_on_the_country() -> None:
    remote = Location(country="DE", workplace=Workplace.REMOTE)
    assert replace(ALERT, location=remote).fuzzy_key.endswith("|DE:")


def test_a_posting_lists_all_its_places_its_main_one_first() -> None:
    vienna = Location(country="AT", city="Vienna")
    assert replace(ALERT, other_locations=(vienna,)).locations == (ALERT.location, vienna)
    assert ALERT.locations == (ALERT.location,)


def test_a_posting_has_no_employment_type_until_a_source_says_so() -> None:
    assert ALERT.employment is None
    assert replace(ALERT, employment=Employment.FULL_TIME).employment is Employment.FULL_TIME
