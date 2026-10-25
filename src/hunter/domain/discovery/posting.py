"""One job as one source shows it, in the shape every source is mapped to."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from hunter.domain.discovery.identity import company_key, text_key, title_key
from hunter.domain.discovery.location import Location


class Employment(Enum):
    FULL_TIME = "full-time"
    PART_TIME = "part-time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"


@dataclass(frozen=True)
class SourceRef:
    """Which source showed the posting, and that source's own id for it."""

    source: str
    native_id: str


@dataclass(frozen=True)
class EmployerRef:
    """The job on the employer's own applicant tracking system: where Hunter can apply."""

    ats: str
    board: str
    job_id: str

    @property
    def key(self) -> str:
        return f"{self.ats}:{self.board}:{self.job_id}"


@dataclass(frozen=True)
class Posting:
    title: str
    company: str
    location: Location
    source: SourceRef
    employer: EmployerRef | None = None
    employment: Employment | None = None
    url: str | None = None
    apply_url: str | None = None
    description: str = ""
    posted_at: datetime | None = None
    other_locations: tuple[Location, ...] = ()
    # The source offers its own one-step application: Indeed's "Schnellbewerbung", LinkedIn's
    # Easy Apply. A later apply route can use it.
    quick_apply: bool = False
    # Other sources' ids for this very posting: EURES shows the Bundesagentur's jobs as its own.
    same_as: tuple[SourceRef, ...] = ()

    @property
    def locations(self) -> tuple[Location, ...]:
        """Every place the job is open in, its main one first."""
        return (self.location, *self.other_locations)

    @property
    def exact_key(self) -> str | None:
        """The same job everywhere, when the employer's own system is known."""
        return self.employer.key if self.employer else None

    @property
    def fuzzy_key(self) -> str:
        """The same job across sources that don't know the employer's system."""
        place = f"{self.location.country or ''}:{text_key(self.location.city or '')}"
        return f"{company_key(self.company)}|{title_key(self.title)}|{place}"
