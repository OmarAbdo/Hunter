"""One company's Recruitee board (docs/sources.md): `<board>.recruitee.com/api/offers/`, where the
board is the company's subdomain. Each offer says whether it's remote, hybrid or on site."""

from typing import Any

from hunter.adapters.html_text import plain_text
from hunter.adapters.sources.reading import employment_from, parsed_time, place_at, read_json
from hunter.adapters.web_client import WebClient
from hunter.domain.discovery.location import Workplace
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

API = "https://{board}.recruitee.com"


class RecruiteeFeed:
    def __init__(self, web: WebClient, board: str, company: str, api: str = API) -> None:
        self.web = web
        self.board = board
        self.company = company
        self.api = api.format(board=board)

    @property
    def name(self) -> str:
        return f"recruitee:{self.board}"

    def fetch(self) -> list[Posting]:
        answer = read_json(self.web, f"{self.api}/api/offers/")
        return [self._posting(offer) for offer in answer["offers"]]

    def _posting(self, offer: dict[str, Any]) -> Posting:
        workplace = workplace_of(offer)
        cities = offer.get("locations") or [offer]
        place, *other_places = [
            place_at(f"{city.get('city') or ''}, {city.get('country_code') or ''}", workplace)
            for city in cities
        ]
        offer_id = str(offer["id"])
        return Posting(
            title=offer["title"].strip(),
            company=offer.get("company_name") or self.company,
            location=place,
            other_locations=tuple(other_places),
            source=SourceRef(source="recruitee", native_id=offer_id),
            employer=EmployerRef(ats="recruitee", board=self.board, job_id=offer_id),
            employment=employment_from(offer.get("employment_type_code")),
            url=offer.get("careers_url"),
            apply_url=offer.get("careers_apply_url"),
            description=plain_text(offer.get("description")),
            posted_at=parsed_time(offer.get("published_at")),
        )


def workplace_of(offer: dict[str, Any]) -> Workplace | None:
    if offer.get("remote"):
        return Workplace.REMOTE
    if offer.get("hybrid"):
        return Workplace.HYBRID
    return Workplace.ONSITE if offer.get("on_site") else None
