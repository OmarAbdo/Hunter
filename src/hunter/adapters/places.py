"""Places from the free text job sources write ("Berlin, Germany", "Remote - EMEA", "Home Office"),
read with the GeoNames data in geonamescache: offline, and no hand-kept city lists.

- A country named in the text decides between cities of one name; otherwise the largest city wins.
- Words like "remote" make the job remote. The countries and regions the text names are then its
  remote scope."""

import json
import re
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import Any

from hunter.domain.discovery.identity import text_key
from hunter.domain.discovery.location import WORLDWIDE, Location, Workplace

REMOTE = re.compile(r"\b(remote|home ?office|work from home|wfh|distributed|anywhere)\b", re.I)
HYBRID = re.compile(r"\bhybrid\b", re.I)
SEPARATORS = re.compile(r"[,/|;()\-–—]+")
REGIONS = {
    "emea": {"EUROPE", "GCC"},
    "europe": {"EUROPE"},
    "eu": {"EU"},
    "european union": {"EU"},
    "eea": {"EEA"},
    "dach": {"DACH"},
    "gcc": {"GCC"},
    "north america": {"NORTH_AMERICA"},
    "worldwide": {WORLDWIDE},
    "anywhere": {WORLDWIDE},
    "global": {WORLDWIDE},
}
COUNTRY_ALIASES = {
    "deutschland": "DE",
    "uk": "GB",
    "england": "GB",
    "usa": "US",
    "united states of america": "US",
    "uae": "AE",
    "emirates": "AE",
    "schweiz": "CH",
    "osterreich": "AT",
    "holland": "NL",
    "ksa": "SA",
}
# Other-language names are read for cities this large: München, Köln, Wien. Smaller towns keep
# their GeoNames name only, which keeps the index small.
ALTERNATE_NAMES_FROM = 100_000
SHORTEST_CITY_NAME = 3
CAPITAL_COUNTRY_CODE = re.compile(r"[A-Z]{2}")


@dataclass(frozen=True)
class City:
    name: str
    country: str
    population: int


def geonames(file_name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (files("geonamescache") / "data" / file_name).read_text("utf-8")
    )
    return data


@cache
def countries_by_name() -> dict[str, str]:
    names = {}
    for record in geonames("countries.json").values():
        names[text_key(record["name"])] = record["iso"]
        names[text_key(record["iso3"])] = record["iso"]
    return names | COUNTRY_ALIASES


@cache
def cities_by_name() -> dict[str, list[City]]:
    index: dict[str, list[City]] = {}
    for record in geonames("cities15000.json").values():
        city = City(record["name"], record["countrycode"], int(record["population"]))
        for key in city_keys(record):
            index.setdefault(key, []).append(city)
    return index


def city_keys(record: dict[str, Any]) -> set[str]:
    """The city's GeoNames name and, for large cities, its other-language names. Airport codes
    and names in other scripts are left out."""
    names = [record["name"]]
    if int(record["population"]) >= ALTERNATE_NAMES_FROM:
        names += [name for name in record["alternatenames"] if not name.isupper()]
    return {key for key in map(text_key, names) if len(key) >= SHORTEST_CITY_NAME}


def country_named(piece: str) -> str | None:
    """A country name, a three-letter code, or a two-letter code written in capitals."""
    code = piece.strip()
    if CAPITAL_COUNTRY_CODE.fullmatch(code) and code in countries_by_name().values():
        return code
    return countries_by_name().get(text_key(piece))


def city_named(piece: str, country: str | None) -> City | None:
    candidates = [
        city
        for city in cities_by_name().get(text_key(piece), [])
        if country is None or city.country == country
    ]
    return max(candidates, key=lambda city: city.population, default=None)


def remote_scope(text: str, named_countries: set[str]) -> frozenset[str]:
    words = text_key(text)
    regions = {
        code
        for phrase, codes in REGIONS.items()
        if re.search(rf"\b{phrase}\b", words)
        for code in codes
    }
    return frozenset(regions | named_countries)


def workplace_in(text: str) -> Workplace | None:
    if HYBRID.search(text):
        return Workplace.HYBRID
    if REMOTE.search(text):
        return Workplace.REMOTE
    return None


def place_from_text(text: str, default_country: str | None = None) -> Location:
    """`default_country` is for sources whose places are all in one country (de.indeed.com)."""
    pieces = [piece for piece in SEPARATORS.split(text) if piece.strip()]
    named = {code for piece in pieces if (code := country_named(piece))}
    country = next(iter(named), None) if len(named) == 1 else None
    city = next((found for piece in pieces if (found := city_named(piece, country))), None)
    workplace = workplace_in(text)
    return Location(
        country=country or (city.country if city else default_country),
        city=city.name if city else None,
        workplace=workplace,
        remote_scope=remote_scope(text, named) if workplace is Workplace.REMOTE else frozenset(),
    )
