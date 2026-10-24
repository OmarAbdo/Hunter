import pytest

from hunter.domain.discovery.location import WORLDWIDE, Location, Workplace, expand_scope


def test_regions_expand_to_countries() -> None:
    assert {"DE", "AT", "CH"} == expand_scope({"DACH"})
    assert "FR" in expand_scope({"EU"})
    assert "NO" in expand_scope({"EEA"})
    assert "NO" not in expand_scope({"EU"})
    assert {"GB", "CH", "DE"} <= expand_scope({"EUROPE"})
    assert "AE" in expand_scope({"GCC"})
    assert {"US", "CA"} == expand_scope({"NORTH_AMERICA"})


def test_countries_stay_as_they_are() -> None:
    assert {"DE", "PL"} == expand_scope({"DE", "PL"})


def test_an_onsite_job_is_reachable_only_from_its_own_country() -> None:
    berlin = Location(country="DE", city="Berlin", workplace=Workplace.ONSITE)
    assert berlin.reachable_from("DE")
    assert not berlin.reachable_from("AE")


def test_a_hybrid_job_counts_as_onsite_for_reach() -> None:
    assert not Location(country="NL", workplace=Workplace.HYBRID).reachable_from("DE")


def test_a_remote_job_is_reachable_from_its_scope() -> None:
    emea = Location(workplace=Workplace.REMOTE, remote_scope=frozenset({"EU"}))
    assert emea.reachable_from("DE")
    assert not emea.reachable_from("US")


def test_a_worldwide_remote_job_is_reachable_from_anywhere() -> None:
    anywhere = Location(workplace=Workplace.REMOTE, remote_scope=frozenset({WORLDWIDE}))
    assert anywhere.reachable_from("AE")


def test_a_remote_job_without_scope_is_reachable_from_its_country_only() -> None:
    listed_in_germany = Location(country="DE", workplace=Workplace.REMOTE)
    assert listed_in_germany.reachable_from("DE")
    assert not listed_in_germany.reachable_from("FR")
    assert not Location(workplace=Workplace.REMOTE).reachable_from("DE")


def test_an_unknown_place_is_reachable_from_nowhere() -> None:
    assert not Location().reachable_from("DE")


def test_country_codes_are_upper_case() -> None:
    with pytest.raises(ValueError, match="ISO 3166"):
        Location(country="de")
