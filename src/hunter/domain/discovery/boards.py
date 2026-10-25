"""Which board on an applicant tracking system (ATS) a link points at. Every link Hunter sees can
name a company's board, and that's how the company registry fills itself."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Board:
    """A company's job board on one ATS. `slug` is the company's name on that system."""

    ats: str
    slug: str

    @property
    def key(self) -> str:
        return f"{self.ats}:{self.slug}"


# Each ATS: the link pattern, and how the parts it captures make the slug.
LINK_PATTERNS = tuple(
    (ats, re.compile(pattern), slug)
    for ats, pattern, slug in (
        (
            "greenhouse",
            r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?([\w-]+)",
            "{0}",
        ),
        ("lever", r"jobs(?:\.eu)?\.lever\.co/([\w.-]+)", "{0}"),
        ("ashby", r"jobs\.ashbyhq\.com/([\w.-]+)", "{0}"),
        ("workable", r"apply\.workable\.com/([\w-]+)", "{0}"),
        ("personio", r"//([a-z0-9-]+)\.jobs\.personio\.(de|com)\b", "{0}.{1}"),
        ("smartrecruiters", r"(?:jobs|careers)\.smartrecruiters\.com/([\w-]+)", "{0}"),
        ("recruitee", r"//([a-z0-9-]+)\.recruitee\.com\b", "{0}"),
        ("teamtailor", r"//([a-z0-9-]+)\.teamtailor\.com\b", "{0}"),
        (
            "workday",
            r"//([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([\w-]+)",
            "{0}/{1}/{2}",
        ),
        ("dvinci", r"//([a-z0-9-]+)\.dvinci-easy\.com\b", "{0}"),
        ("softgarden", r"//([a-z0-9-]+)\.softgarden\.io\b", "{0}"),
        ("coveto", r"//(k\d+)\.coveto\.de\b", "{0}"),
        ("onlyfy", r"//([a-z0-9-]+)\.onlyfy\.jobs\b", "{0}"),
        ("join", r"join\.com/companies/([\w-]+)", "{0}"),
        # A SuccessFactors career site is on the company's own host, so it's known by the shape
        # of its job links, `/job/<title>/<id>/`; it comes last, after every system with a host
        # of its own.
        (
            "successfactors",
            r"//([a-z0-9-]+(?:\.[a-z0-9-]+)+)/(?:[a-z]{2}(?:_[A-Z]{2})?/)?job/[^/?#]+/\d{8,}/",
            "{0}",
        ),
    )
)
# Path parts that aren't companies. `j` is Workable's job link (apply.workable.com/j/<shortcode>).
NOT_SLUGS = frozenset({"embed", "api", "v1", "jobs", "www", "careers", "app", "j"})


def board_from_link(link: str) -> Board | None:
    for ats, pattern, slug in LINK_PATTERNS:
        found = pattern.search(link)
        if found and found.group(1).lower() not in NOT_SLUGS:
            return Board(ats=ats, slug=slug.format(*found.groups()))
    return None


def board_from_key(key: str) -> Board | None:
    """The board a feed's name (`ats:slug`) stands for, or None for a source that isn't a board."""
    ats, colon, slug = key.partition(":")
    known = {known_ats for known_ats, _, _ in LINK_PATTERNS}
    return Board(ats=ats, slug=slug) if colon and slug and ats in known else None
