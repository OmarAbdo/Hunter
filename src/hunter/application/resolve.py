"""Resolving: a job seen only on job boards (an Indeed alert, the Bundesagentur) is linked to the
employer's own posting once the company's board is known and shows it. The two become one job,
with every sighting kept. That's where Hunter can apply."""

from hunter.application.ports import JobLinks
from hunter.domain.discovery.identity import company_key
from hunter.domain.discovery.posting import Posting
from hunter.domain.discovery.resolution import employer_posting


def resolve(links: JobLinks) -> int:
    """How many job-board jobs were linked to their employer's posting."""
    employer_jobs: dict[str, list[tuple[int, Posting]]] = {}
    linked = 0
    for job_id, posting in links.unresolved():
        key = company_key(posting.company)
        if key not in employer_jobs:
            employer_jobs[key] = links.employer_jobs(key)
        employer = employer_posting(posting, employer_jobs[key])
        if employer is not None:
            links.merge(job_id, into=employer)
            linked += 1
    return linked
