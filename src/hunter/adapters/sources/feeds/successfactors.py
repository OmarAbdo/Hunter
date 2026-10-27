"""One company's SAP SuccessFactors career site (docs/sources.md), of either kind.

A site built with its Career Site Builder is on the company's own host (`jobs.bechtle.com`), which
is the board. Every such site serves all of its jobs as RSS at `/sitemal.xml`, a feed SAP doesn't
document but every instance has. Each job gives its place as "town, country, postcode" (or "town,
state, state name, country"), which its title repeats in brackets.

A classic career portal is on one of SAP's shared hosts, told apart by the company id
(`career5.successfactors.eu/career?company=beiersdorfP`); its board is the host and the id
(`career5.successfactors.eu/beiersdorfP`; ids are case-sensitive). Its job list comes as XML, all
in one answer: title, HTML description and requisition id, sometimes the date, a location and
filters each company names itself ("Posting Country", "City", "Employment Type", "Volume"). It
names neither the company nor a link, and a company it doesn't know gets an HTML page. SAP's
robots.txt on these hosts turns every bot away, so Hunter reads them with a browser's identity."""

import html
import re
from datetime import UTC, datetime
from xml.etree import ElementTree

from hunter.adapters.html_text import plain_text
from hunter.adapters.sources.reading import employment_from, place_at, read_text
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

API = "https://{host}"
GOOGLE = "{http://base.google.com/ns/1.0}"
COUNTRY_CODE = re.compile(r"[A-Z]{2}")
CLASSIC_JOB = "https://{host}/career?company={company_id}&career_ns=job_listing&career_job_req_id="
BROWSER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
}
NAMELESS = re.compile(r"<>[^<]*</>")  # AIIB's list holds `<>101</>`, which isn't XML


class SuccessFactorsFeed:
    def __init__(self, web: WebClient, board: str, company: str, api: str = API) -> None:
        self.web = web
        self.board = board
        self.company = company
        self.host, _, self.company_id = board.partition("/")
        self.api = api.format(host=self.host)

    @property
    def name(self) -> str:
        return f"successfactors:{self.board}"

    def fetch(self) -> list[Posting]:
        if self.company_id:
            return [self._classic_posting(job) for job in self._classic_jobs()]
        text = read_text(self.web, f"{self.api}/sitemal.xml")
        try:
            channel = ElementTree.fromstring(text).find("channel")
        except ElementTree.ParseError as error:
            raise SourceUnavailableError(f"{self.name}: not RSS ({error})") from error
        if channel is None:
            raise SourceUnavailableError(f"{self.name}: an RSS feed without a channel")
        return [self._posting(item) for item in channel.findall("item")]

    def _posting(self, item: ElementTree.Element) -> Posting:
        where = (item.findtext(f"{GOOGLE}location") or "").strip()
        title = (item.findtext("title") or "").strip().removesuffix(f"({where})").strip()
        job_id = (item.findtext("guid") or "").strip()
        link = (item.findtext("link") or "").strip()
        return Posting(
            title=title,
            company=(item.findtext(f"{GOOGLE}employer") or "").strip() or self.company,
            location=place_of(where),
            source=SourceRef(source="successfactors", native_id=job_id),
            employer=EmployerRef(ats="successfactors", board=self.board, job_id=job_id),
            url=link,
            apply_url=link,
            description=plain_text(html.unescape(item.findtext("description") or "")),
        )

    def _classic_jobs(self) -> list[ElementTree.Element]:
        query = {
            "company": self.company_id,
            "career_ns": "job_listing_summary",
            "resultType": "XML",
        }
        text = read_text(self.web, f"{self.api}/career", query, BROWSER)
        try:
            listing = ElementTree.fromstring(NAMELESS.sub("", text))
        except ElementTree.ParseError as error:
            raise SourceUnavailableError(f"{self.name}: not a job listing ({error})") from error
        if listing.tag != "Job-Listing":
            raise SourceUnavailableError(f"{self.name}: no job listing; is the company id right?")
        return listing.findall("Job")

    def _classic_posting(self, job: ElementTree.Element) -> Posting:
        job_id = (job.findtext("ReqId") or "").strip()  # the requisition's id
        filters = filters_of(job)
        city = (job.findtext("Location") or "").strip() or labelled(filters, "city")
        link = CLASSIC_JOB.format(host=self.host, company_id=self.company_id) + job_id
        return Posting(
            title=html.unescape((job.findtext("JobTitle") or "").strip()),
            company=self.company,
            location=place_at(", ".join(filter(None, (city, labelled(filters, "country")))), None),
            source=SourceRef(source="successfactors", native_id=job_id),
            employer=EmployerRef(ats="successfactors", board=self.board, job_id=job_id),
            employment=employment_from(labelled(filters, "employment", "volume")),
            url=link,
            apply_url=link,
            description=plain_text(job.findtext("Job-Description") or ""),
            posted_at=posted_on((job.findtext("Posted-Date") or "").strip()),
        )


def place_of(where: str) -> Location:
    """The town comes first, and the country is the last part that's a two-letter code: "Budapest,
    HU, 1037", "Morristown, NJ, New Jersey, US"."""
    parts = [part.strip() for part in where.split(",")]
    codes = [part for part in parts[1:] if COUNTRY_CODE.fullmatch(part)]
    return place_at(f"{parts[0]}, {codes[-1]}" if codes else parts[0], None)


def filters_of(job: ElementTree.Element) -> dict[str, str]:
    """A classic job's filters (`<filter1><label>City</label><value>Wien</value></filter1>`) by
    their label in lower case, where they have a value."""
    pairs = (
        ((part.findtext("label") or "").strip().lower(), (part.findtext("value") or "").strip())
        for part in job
        if part.tag.startswith("filter")
    )
    return {label: value for label, value in pairs if value}


def labelled(filters: dict[str, str], *words: str) -> str:
    """The value of the first filter whose label holds one of the words."""
    found = (value for label, value in filters.items() if any(word in label for word in words))
    return next(found, "")


def posted_on(text: str) -> datetime | None:
    """A classic job's date, written "10/21/2026"."""
    try:
        return datetime.strptime(text, "%m/%d/%Y").replace(tzinfo=UTC) if text else None
    except ValueError:
        return None
