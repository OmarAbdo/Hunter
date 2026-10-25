"""One company's d.vinci portal (docs/sources.md): the public list of job publications at
`<board>.dvinci-easy.com/jobPublication/list.json`, where the board is the portal's subdomain. One
portal can hold several companies of a group, and one opening can be advertised in several
publications; the first one stands for the opening."""

from typing import Any

from hunter.adapters.html_text import plain_text
from hunter.adapters.sources.reading import parsed_time, place_at, read_json
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

API = "https://{board}.dvinci-easy.com"
TEXTS = ("introduction", "tasks", "profile", "weOffer", "closingText")


class DvinciFeed:
    def __init__(self, web: WebClient, board: str, company: str, api: str = API) -> None:
        self.web = web
        self.board = board
        self.company = company
        self.api = api.format(board=board)

    @property
    def name(self) -> str:
        return f"dvinci:{self.board}"

    def fetch(self) -> list[Posting]:
        answer = read_json(self.web, f"{self.api}/jobPublication/list.json")
        if not isinstance(answer, list):
            raise SourceUnavailableError(f"{self.name}: an answer that isn't a job list")
        openings: dict[str, dict[str, Any]] = {}
        for publication in answer:
            openings.setdefault(str(publication["jobOpening"]["id"]), publication)
        return [self._posting(opening, advert) for opening, advert in openings.items()]

    def _posting(self, opening_id: str, publication: dict[str, Any]) -> Posting:
        opening = publication["jobOpening"]
        place, *other_places = [place_of(where) for where in opening.get("locations") or [{}]]
        return Posting(
            title=publication["position"].strip(),
            company=(opening.get("company") or {}).get("name") or self.company,
            location=place,
            other_locations=tuple(other_places),
            source=SourceRef(source="dvinci", native_id=opening_id),
            employer=EmployerRef(ats="dvinci", board=self.board, job_id=opening_id),
            url=publication.get("jobPublicationURL"),
            apply_url=publication.get("applicationFormURL"),
            description="\n\n".join(plain_text(publication.get(part)) for part in TEXTS).strip(),
            posted_at=parsed_time(opening.get("createdDate")),
        )


def place_of(where: dict[str, Any]) -> Location:
    """The address's town where there is one: a place's name can be a site ("Mertingen (nördlich
    von Augsburg)")."""
    country = (where.get("country") or {}).get("isoA2") or ""
    town = (where.get("address") or {}).get("city") or where.get("name") or ""
    return place_at(f"{town}, {country}", None)
