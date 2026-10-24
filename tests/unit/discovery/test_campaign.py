from dataclasses import replace

from hunter.domain.discovery.campaign import Campaign, Rejection
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import Employment, Posting, SourceRef

PILOT = Campaign(
    id="de-swe-berlin",
    title="Full-time software jobs in Berlin",
    home="DE",
    countries=frozenset({"DE"}),
    cities=frozenset({"Berlin"}),
    employment=frozenset({Employment.FULL_TIME}),
    roles=("engineer", "developer", "entwickler"),
    excluded_roles=("working student", "werkstudent", "intern\\b"),
)
JOB = Posting(
    title="Senior Backend Engineer (m/w/d)",
    company="Nextcloud",
    location=Location(country="DE", city="Berlin", workplace=Workplace.HYBRID),
    source=SourceRef(source="greenhouse", native_id="4711"),
    employment=Employment.FULL_TIME,
)


def test_a_job_that_fits_every_rule_is_matched() -> None:
    assert PILOT.rejects(JOB) is None


def test_a_title_that_fits_no_role_is_rejected() -> None:
    assert PILOT.rejects(replace(JOB, title="Account Executive")) is Rejection.ROLE


def test_an_excluded_role_is_rejected_even_when_a_role_fits() -> None:
    working_student = replace(JOB, title="Working Student Software Engineer")
    assert PILOT.rejects(working_student) is Rejection.EXCLUDED_ROLE


def test_roles_ignore_case() -> None:
    assert PILOT.rejects(replace(JOB, title="SOFTWARE ENTWICKLER")) is None


def test_an_onsite_job_in_another_city_is_rejected() -> None:
    munich = replace(JOB, location=Location(country="DE", city="Munich"))
    assert PILOT.rejects(munich) is Rejection.PLACE


def test_an_onsite_job_in_another_country_is_rejected() -> None:
    dubai = replace(JOB, location=Location(country="AE", city="Dubai"))
    assert PILOT.rejects(dubai) is Rejection.PLACE


def test_a_remote_job_open_to_home_is_matched_wherever_it_is_listed() -> None:
    remote = Location(country="NL", workplace=Workplace.REMOTE, remote_scope=frozenset({"EU"}))
    assert PILOT.rejects(replace(JOB, location=remote)) is None


def test_a_remote_job_closed_to_home_is_rejected() -> None:
    remote = Location(country="US", workplace=Workplace.REMOTE, remote_scope=frozenset({"US"}))
    assert PILOT.rejects(replace(JOB, location=remote)) is Rejection.PLACE


def test_a_workplace_the_campaign_does_not_take_is_rejected() -> None:
    onsite_only = replace(PILOT, workplaces=frozenset({Workplace.ONSITE}))
    assert onsite_only.rejects(JOB) is Rejection.WORKPLACE


def test_an_unknown_workplace_counts_as_onsite() -> None:
    remote_only = replace(PILOT, workplaces=frozenset({Workplace.REMOTE}))
    unknown = replace(JOB, location=Location(country="DE", city="Berlin"))
    assert remote_only.rejects(unknown) is Rejection.WORKPLACE


def test_another_employment_type_is_rejected() -> None:
    part_time = replace(JOB, employment=Employment.PART_TIME)
    assert PILOT.rejects(part_time) is Rejection.EMPLOYMENT


def test_an_unknown_employment_type_is_matched() -> None:
    assert PILOT.rejects(replace(JOB, employment=None)) is None


def test_a_campaign_without_cities_takes_the_whole_country() -> None:
    germany = replace(PILOT, cities=frozenset())
    munich = replace(JOB, location=Location(country="DE", city="München"))
    assert germany.rejects(munich) is None


def test_cities_are_compared_by_their_normalised_names() -> None:
    zurich = replace(PILOT, countries=frozenset({"CH"}), cities=frozenset({"Zurich"}))
    assert zurich.rejects(replace(JOB, location=Location(country="CH", city="Zürich"))) is None
