"""What the GUI shows, read from the pool and the registry as plain JSON-ready values: each campaign
with what it took and why it turned jobs down, a campaign's jobs, the companies with their boards,
the size of the pool, and how many taken jobs have their whole ad."""

import sqlite3
from collections import Counter
from collections.abc import Sequence
from typing import Any

from hunter.adapters.storage.matches import Matches
from hunter.adapters.storage.pool import Pool, decoded
from hunter.adapters.storage.registry import Registry
from hunter.domain.ads.coverage import AdState, TakenJob, coverage
from hunter.domain.discovery.campaign import Campaign
from hunter.domain.discovery.location import Location


def campaigns_view(database: sqlite3.Connection, campaigns: Sequence[Campaign]) -> list[Any]:
    """`judged` is every job the campaign looked at: those it took and those it turned down."""
    matches = Matches(database)
    shown = []
    for campaign in campaigns:
        taken = len(matches.matched(campaign.id))
        rejections = matches.rejections(campaign.id)
        shown.append(
            {
                "id": campaign.id,
                "title": campaign.title,
                "judged": taken + sum(rejections.values()),
                "taken": taken,
                "turned_down": {reason.value: count for reason, count in rejections.items()},
            }
        )
    return shown


TAKEN = "SELECT job_id FROM matches WHERE campaign_id = ? AND rejection IS NULL"
# A job with what reading its ad found: gone, or the whole ad read.
WITH_AD = (
    "SELECT id, posting, id IN (SELECT job_id FROM gone), id IN (SELECT job_id FROM whole_ads) "
    "FROM jobs"
)


def jobs_view(database: sqlite3.Connection, campaign_id: str) -> list[Any]:
    """The campaign's jobs, the newest first. Two queries for all of them, not two a job: a
    campaign takes well over a thousand."""
    rows = database.execute(f"{WITH_AD} WHERE id IN ({TAKEN})", (campaign_id,))
    sources: dict[int, list[str]] = {}
    seen = f"SELECT job_id, source FROM sightings WHERE job_id IN ({TAKEN}) ORDER BY rowid"
    for job_id, source in database.execute(seen, (campaign_id,)):
        sources.setdefault(job_id, []).append(source)
    jobs = [
        job_of(job_id, taken_job(posting, gone, read), sources.get(job_id, []))
        for job_id, posting, gone, read in rows
    ]
    return sorted(jobs, key=lambda job: job["posted_at"] or "", reverse=True)


def job_of(job_id: int, job: TakenJob, sources: list[str]) -> dict[str, Any]:
    posting = job.posting
    return {
        "id": job_id,
        "title": posting.title,
        "company": posting.company,
        "places": [place_text(place) for place in posting.locations],
        "workplace": posting.location.workplace.value if posting.location.workplace else None,
        "employment": posting.employment.value if posting.employment else None,
        "posted_at": f"{posting.posted_at:%Y-%m-%d}" if posting.posted_at else None,
        "url": posting.url,
        "ad": job.state.value,
        "apply_url": posting.apply_url,
        "employer_system": posting.employer.ats if posting.employer else None,
        "sources": list(dict.fromkeys(sources)),
    }


def place_text(place: Location) -> str:
    return ", ".join(part for part in (place.city, place.country) if part) or "unknown"


def companies_view(database: sqlite3.Connection) -> list[Any]:
    return [
        {
            "name": company.name,
            "website": company.website,
            "boards": [
                {"board": board.key, "status": status.value}
                for board, status in company.feeds.items()
            ],
        }
        for company in Registry(database).all()
    ]


def pool_view(database: sqlite3.Connection) -> dict[str, int]:
    companies = Registry(database).all()
    return {
        "jobs": Pool(database).job_count(),
        "companies": len(companies),
        "boards": sum(len(company.boards) for company in companies),
    }


def ads_view(database: sqlite3.Connection) -> dict[str, Any]:
    """The jobs any campaign took, by source, the biggest first, counted by how much of their ad
    Hunter has."""
    counts = coverage(Pool(database).taken())
    bysize = sorted(counts.items(), key=lambda item: (-item[1].total(), item[0]))
    return {
        "sources": [{"source": source, **ad_counts(states)} for source, states in bysize],
        "total": ad_counts(sum(counts.values(), Counter())),
    }


def ad_counts(states: Counter[AdState]) -> dict[str, int]:
    return {"taken": states.total(), **{state.value: states[state] for state in AdState}}


def ad_view(database: sqlite3.Connection, job_id: int) -> dict[str, Any] | None:
    """One job's ad as Hunter has it, and how much of it that is; None for an unknown job."""
    row = database.execute(f"{WITH_AD} WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    job = taken_job(*row[1:])
    return {
        "id": job_id,
        "title": job.posting.title,
        "company": job.posting.company,
        "url": job.posting.url,
        "ad": job.state.value,
        "text": job.posting.description,
    }


def taken_job(posting: str, gone: int, read: int) -> TakenJob:
    return TakenJob(decoded(posting), gone=bool(gone), read=bool(read))
