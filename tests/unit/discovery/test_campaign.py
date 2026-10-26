from dataclasses import replace
from datetime import UTC, datetime, timedelta

from hunter.domain.discovery.campaign import Campaign, Rejection, Search
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


def test_a_job_open_in_several_places_is_taken_when_one_of_them_fits() -> None:
    barcelona = Location(country="ES", city="Barcelona")
    several = replace(JOB, location=barcelona, other_locations=(JOB.location,))
    assert PILOT.rejects(several) is None


def test_a_job_open_in_several_places_none_of_which_fit_is_rejected_for_the_first() -> None:
    barcelona, dubai = Location(country="ES", city="Barcelona"), Location(country="AE")
    assert PILOT.rejects(replace(JOB, location=barcelona, other_locations=(dubai,))) is (
        Rejection.PLACE
    )


def test_cities_are_compared_by_their_normalised_names() -> None:
    zurich = replace(PILOT, countries=frozenset({"CH"}), cities=frozenset({"Zurich"}))
    assert zurich.rejects(replace(JOB, location=Location(country="CH", city="Zürich"))) is None


def test_a_campaign_names_its_searches() -> None:
    search = Search(source="bundesagentur", query="Softwareentwickler", place="Berlin")
    assert replace(PILOT, searches=(search,)).searches == (search,)
    assert PILOT.searches == ()
    assert Search(source="eures", query="software engineer").place == ""
    assert len({search, replace(search)}) == 1  # a value: the same search counts once


def test_a_search_names_no_country_unless_it_says() -> None:
    assert Search(source="bundesagentur", query="Softwareentwickler").country == ""


NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


def test_a_job_older_than_the_campaign_allows_is_turned_down() -> None:
    fresh_only = replace(PILOT, max_age_days=30)
    old = replace(JOB, posted_at=NOW - timedelta(days=31))
    assert fresh_only.rejects(old, NOW) is Rejection.TOO_OLD
    assert fresh_only.rejects(replace(old, posted_at=NOW - timedelta(days=30)), NOW) is None


def test_a_job_of_unknown_age_is_taken() -> None:
    fresh_only = replace(PILOT, max_age_days=30)
    assert fresh_only.rejects(replace(JOB, posted_at=None), NOW) is None


def test_a_campaign_without_an_age_limit_takes_old_jobs() -> None:
    old = replace(JOB, posted_at=NOW - timedelta(days=400))
    assert PILOT.rejects(old, NOW) is None


def test_age_is_judged_only_when_the_time_is_given() -> None:
    old = replace(JOB, posted_at=NOW - timedelta(days=400))
    assert replace(PILOT, max_age_days=30).rejects(old) is None
