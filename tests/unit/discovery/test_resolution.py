from dataclasses import replace

from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef
from hunter.domain.discovery.resolution import employer_posting, same_job

SEEN = Posting(
    title="Senior Backend Engineer (m/w/d)",
    company="N26 GmbH",
    location=Location(country="DE", city="Berlin"),
    source=SourceRef(source="indeed-alert", native_id="abc123"),
)
EMPLOYER = Posting(
    title="Senior Backend Engineer (all genders)",
    company="N26",
    location=Location(country="DE", city="Berlin", workplace=Workplace.HYBRID),
    source=SourceRef(source="greenhouse", native_id="4711"),
    employer=EmployerRef(ats="greenhouse", board="n26", job_id="4711"),
)


def test_the_same_title_in_the_same_place_is_the_same_job() -> None:
    assert same_job(SEEN, EMPLOYER)


def test_another_title_is_another_job() -> None:
    assert not same_job(replace(SEEN, title="Backend Engineer"), EMPLOYER)


def test_another_city_is_another_job() -> None:
    assert not same_job(replace(SEEN, location=Location(country="DE", city="Munich")), EMPLOYER)


def test_another_country_is_another_job() -> None:
    assert not same_job(replace(SEEN, location=Location(country="AT", city="Berlin")), EMPLOYER)


def test_a_place_without_a_city_fits_any_city_in_its_country() -> None:
    assert same_job(replace(SEEN, location=Location(country="DE")), EMPLOYER)
    assert same_job(SEEN, replace(EMPLOYER, location=Location(country="DE")))


def test_one_of_several_places_is_enough() -> None:
    munich = Location(country="DE", city="München")
    assert same_job(replace(SEEN, location=munich), replace(EMPLOYER, other_locations=(munich,)))


def test_cities_are_compared_by_their_normalised_names() -> None:
    assert same_job(
        replace(SEEN, location=Location(country="CH", city="Zürich")),
        replace(EMPLOYER, location=Location(country="CH", city="Zurich")),
    )


def test_the_one_employer_posting_that_fits_is_the_job() -> None:
    other = replace(EMPLOYER, title="Data Engineer")
    assert employer_posting(SEEN, [(1, other), (2, EMPLOYER)]) == 2


def test_no_posting_that_fits_is_no_job() -> None:
    assert employer_posting(SEEN, [(1, replace(EMPLOYER, title="Data Engineer"))]) is None
    assert employer_posting(SEEN, []) is None


def test_two_postings_that_fit_leave_it_open() -> None:
    """Two openings with the same title and place: which one was seen can't be told."""
    assert employer_posting(SEEN, [(1, EMPLOYER), (2, EMPLOYER)]) is None
