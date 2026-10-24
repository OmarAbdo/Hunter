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
        ("join", r"join\.com/companies/([\w-]+)", "{0}"),
    )
)
NOT_SLUGS = frozenset({"embed", "api", "v1", "jobs", "www", "careers", "app"})


def board_from_link(link: str) -> Board | None:
    for ats, pattern, slug in LINK_PATTERNS:
        found = pattern.search(link)
        if found and found.group(1).lower() not in NOT_SLUGS:
            return Board(ats=ats, slug=slug.format(*found.groups()))
    return None
