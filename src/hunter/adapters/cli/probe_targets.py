"""Which companies to probe for a board: those with no board whose jobs the campaigns took, most
taken first, and not probed yet. Those are the ones whose jobs Hunter will want to apply to."""

import sqlite3
from collections import Counter

from hunter.adapters.campaign_files import load_campaigns
from hunter.adapters.cli.project import Project
from hunter.adapters.storage.matches import Matches
from hunter.adapters.storage.pool import Pool
from hunter.adapters.storage.probe_log import ProbeLog
from hunter.adapters.storage.registry import Registry
from hunter.domain.discovery.company import Company
from hunter.domain.discovery.identity import company_key


def companies_to_probe(project: Project, database: sqlite3.Connection, limit: int) -> list[Company]:
    pool, matches = Pool(database), Matches(database)
    taken = Counter(
        company_key(pool.posting(job_id).company)
        for campaign in load_campaigns(project.campaigns_folder)
        for job_id in matches.matched(campaign.id)
    )
    registry, probed = Registry(database), ProbeLog(database).probed()
    known = (registry.get(key) for key, _ in taken.most_common())
    return [
        company
        for company in known
        if company is not None and not company.boards and company.key not in probed
    ][:limit]
