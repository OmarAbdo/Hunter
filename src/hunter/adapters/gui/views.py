"""What the GUI shows, read from the pool and the registry as plain JSON-ready values: each campaign
with what it took and why it turned jobs down, a campaign's jobs, the companies with their boards,
and the size of the pool."""

import sqlite3
from collections.abc import Sequence
from typing import Any

from hunter.adapters.storage.matches import Matches
from hunter.adapters.storage.pool import Pool, decoded
from hunter.adapters.storage.registry import Registry
from hunter.domain.discovery.campaign import Campaign
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import Posting


def campaigns_view(database: sqlite3.Connection, campaigns: Sequence[Campaign]) -> list[Any]:
    matches = Matches(database)
    return [
        {
            "id": campaign.id,
            "title": campaign.title,
            "taken": len(matches.matched(campaign.id)),
            "turned_down": {
                reason.value: count for reason, count in matches.rejections(campaign.id).items()
            },
        }
        for campaign in campaigns
    ]


TAKEN = "SELECT job_id FROM matches WHERE campaign_id = ? AND rejection IS NULL"


def jobs_view(database: sqlite3.Connection, campaign_id: str) -> list[Any]:
    """The campaign's jobs, the newest first. Two queries for all of them, not two a job: a
    campaign takes well over a thousand."""
    rows = database.execute(f"SELECT id, posting FROM jobs WHERE id IN ({TAKEN})", (campaign_id,))
    sources: dict[int, list[str]] = {}
    seen = f"SELECT job_id, source FROM sightings WHERE job_id IN ({TAKEN}) ORDER BY rowid"
    for job_id, source in database.execute(seen, (campaign_id,)):
        sources.setdefault(job_id, []).append(source)
    jobs = [job_of(job_id, decoded(posting), sources.get(job_id, [])) for job_id, posting in rows]
    return sorted(jobs, key=lambda job: job["posted_at"] or "", reverse=True)


def job_of(job_id: int, posting: Posting, sources: list[str]) -> dict[str, Any]:
    return {
        "id": job_id,
        "title": posting.title,
        "company": posting.company,
        "places": [place_text(place) for place in posting.locations],
        "workplace": posting.location.workplace.value if posting.location.workplace else None,
        "employment": posting.employment.value if posting.employment else None,
        "posted_at": f"{posting.posted_at:%Y-%m-%d}" if posting.posted_at else None,
        "url": posting.url,
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
