"""Campaign files: `campaigns/<id>.toml`, one kind of job search each. The file name is the
campaign's id. Every setting is checked, so a typo fails loudly instead of quietly widening or
narrowing the search. The repository is public: campaign files hold criteria, nothing personal."""

import tomllib
from pathlib import Path
from typing import Any

from hunter.domain.discovery.campaign import Campaign, Search
from hunter.domain.discovery.location import Workplace
from hunter.domain.discovery.posting import Employment

REQUIRED = ("title", "home", "countries")
OPTIONAL = (
    "cities",
    "workplaces",
    "employment",
    "roles",
    "excluded_roles",
    "searches",
    "max_age_days",
    "languages",
)
SEARCH_SETTINGS = ("source", "query", "place", "country")


class CampaignFileError(Exception):
    pass


def load_campaigns(folder: Path) -> list[Campaign]:
    return [load_campaign(path) for path in sorted(folder.glob("*.toml"))]


def load_campaign(path: Path) -> Campaign:
    try:
        settings = tomllib.loads(path.read_text(encoding="utf-8"))
        check_settings(settings)
        return campaign_from(path.stem, settings)
    except ValueError as error:
        raise CampaignFileError(f"{path.name}: {error}") from error


def check_settings(settings: dict[str, Any]) -> None:
    unknown = sorted(set(settings) - {*REQUIRED, *OPTIONAL})
    if unknown:
        raise ValueError(f"unknown setting {', '.join(unknown)}")
    missing = [name for name in REQUIRED if name not in settings]
    if missing:
        raise ValueError(f"missing {', '.join(missing)}")


def campaign_from(campaign_id: str, settings: dict[str, Any]) -> Campaign:
    """Settings left out take the widest choice: every workplace, any employment, any title."""
    every_workplace = [workplace.value for workplace in Workplace]
    return Campaign(
        id=campaign_id,
        title=str(settings["title"]),
        home=str(settings["home"]),
        countries=frozenset(settings["countries"]),
        cities=frozenset(settings.get("cities", [])),
        workplaces=frozenset(map(Workplace, settings.get("workplaces", every_workplace))),
        employment=frozenset(map(Employment, settings.get("employment", []))),
        roles=tuple(settings.get("roles", [])),
        excluded_roles=tuple(settings.get("excluded_roles", [])),
        max_age_days=settings.get("max_age_days"),
        languages=frozenset(settings.get("languages", [])),
        searches=tuple(map(search_from, settings.get("searches", []))),
    )


def search_from(settings: dict[str, Any]) -> Search:
    """A `[[searches]]` table: `source` and `query`, and `place` and `country` where the search
    has them."""
    unknown = sorted(set(settings) - set(SEARCH_SETTINGS))
    if unknown:
        raise ValueError(f"a search with unknown setting {', '.join(unknown)}")
    if not settings.get("query") or not settings.get("source"):
        raise ValueError("a search without a query or a source")
    return Search(
        source=str(settings["source"]),
        query=str(settings["query"]),
        place=str(settings.get("place", "")),
        country=str(settings.get("country", "")),
    )
