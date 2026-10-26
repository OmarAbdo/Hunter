import pytest

from hunter.adapters.places import place_from_text, places_from_text
from hunter.domain.discovery.location import WORLDWIDE, Location, Workplace


@pytest.mark.parametrize(
    ("text", "place"),
    [
        ("Berlin, Germany", Location(country="DE", city="Berlin")),
        ("Berlin", Location(country="DE", city="Berlin")),
        ("München", Location(country="DE", city="Munich")),
        ("Zürich, Switzerland", Location(country="CH", city="Zürich")),
        ("Dubai - United Arab Emirates", Location(country="AE", city="Dubai")),
        ("London, UK", Location(country="GB", city="London")),
        ("Deutschland", Location(country="DE")),
        ("Frankfurt am Main, Hessen", Location(country="DE", city="Frankfurt am Main")),
    ],
)
def test_cities_and_countries(text: str, place: Location) -> None:
    assert place_from_text(text) == place


@pytest.mark.parametrize(
    ("text", "place"),
    [
        (
            "Remote - Germany",
            Location(country="DE", workplace=Workplace.REMOTE, remote_scope=frozenset({"DE"})),
        ),
        (
            "Remote (EMEA)",
            Location(workplace=Workplace.REMOTE, remote_scope=frozenset({"EUROPE", "GCC"})),
        ),
        (
            "Remote, Europe",
            Location(workplace=Workplace.REMOTE, remote_scope=frozenset({"EUROPE"})),
        ),
        (
            "Anywhere in the world",
            Location(workplace=Workplace.REMOTE, remote_scope=frozenset({WORLDWIDE})),
        ),
        ("Hybrid - Berlin", Location(country="DE", city="Berlin", workplace=Workplace.HYBRID)),
        ("Home Office", Location(workplace=Workplace.REMOTE)),
    ],
)
def test_workplaces_and_remote_scopes(text: str, place: Location) -> None:
    assert place_from_text(text) == place


def test_a_country_in_the_text_decides_between_cities_of_one_name() -> None:
    assert place_from_text("Cambridge, USA") == Location(country="US", city="Cambridge")
    assert place_from_text("Cambridge") == Location(country="GB", city="Cambridge")


def test_two_letter_country_codes_count_only_in_capitals() -> None:
    assert place_from_text("Berlin, DE") == Location(country="DE", city="Berlin")
    assert place_from_text("Frankfurt am Main") == Location(country="DE", city="Frankfurt am Main")


def test_the_largest_city_of_a_name_wins_without_a_country() -> None:
    assert place_from_text("Paris") == Location(country="FR", city="Paris")


def test_a_source_can_say_which_country_its_places_are_in() -> None:
    home_office = Location(country="DE", workplace=Workplace.REMOTE)
    assert place_from_text("Home Office", default_country="DE") == home_office


def test_several_cities_are_several_places() -> None:
    assert places_from_text("Berlin, Vienna, Barcelona") == (
        Location(country="DE", city="Berlin"),
        Location(country="AT", city="Vienna"),
        Location(country="ES", city="Barcelona"),
    )


def test_a_city_and_its_country_are_one_place() -> None:
    assert places_from_text("Berlin, Germany") == (Location(country="DE", city="Berlin"),)


def test_a_place_without_cities_is_one_place() -> None:
    assert places_from_text("Remote") == (Location(workplace=Workplace.REMOTE),)


def test_several_cities_share_the_workplace() -> None:
    assert places_from_text("Hybrid: Berlin / Munich") == (
        Location(country="DE", city="Berlin", workplace=Workplace.HYBRID),
        Location(country="DE", city="Munich", workplace=Workplace.HYBRID),
    )


def test_text_with_no_place_is_an_unknown_place() -> None:
    assert place_from_text("") == Location()
    assert place_from_text("Multiple locations") == Location()


@pytest.mark.parametrize(
    ("text", "city"),
    [
        ("Hanau, DE", "Hanau am Main"),
        ("Marburg", "Marburg an der Lahn"),
        ("Rüsselsheim, Germany", "Rüsselsheim am Main"),
        ("Halle, Deutschland", "Halle (Saale)"),
        ("Frankfurt", "Frankfurt am Main"),
    ],
)
def test_a_town_is_known_by_its_name_without_the_river_or_region(text: str, city: str) -> None:
    """GeoNames calls Hanau "Hanau am Main"; job sources write "Hanau". Of several towns with one
    short name the largest wins, as for any name: Frankfurt am Main, not Frankfurt (Oder)."""
    assert place_from_text(text) == Location(country="DE", city=city)
