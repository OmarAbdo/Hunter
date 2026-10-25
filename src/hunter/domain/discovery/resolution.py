"""Which of an employer's postings a job seen on a job board is: the one with the same title in the
same place. Two that fit leave it open, since which of them was seen can't be told."""

from collections.abc import Sequence

from hunter.domain.discovery.identity import text_key, title_key
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import Posting


def same_place(one: Location, other: Location) -> bool:
    """The same country, and the same city where both name one."""
    if one.country != other.country:
        return False
    return not one.city or not other.city or text_key(one.city) == text_key(other.city)


def same_job(seen: Posting, employer: Posting) -> bool:
    if title_key(seen.title) != title_key(employer.title):
        return False
    return any(same_place(one, other) for one in seen.locations for other in employer.locations)


def employer_posting(seen: Posting, candidates: Sequence[tuple[int, Posting]]) -> int | None:
    """The id of the one candidate that is the seen job, or None."""
    fitting = [job_id for job_id, posting in candidates if same_job(seen, posting)]
    return fitting[0] if len(fitting) == 1 else None
