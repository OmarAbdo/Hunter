"""`discover [--campaign ID]...`: reads every source for the chosen campaigns, all of them when none
is named, and prints the report."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TextIO

from hunter.adapters.campaign_files import CampaignFileError, load_campaigns
from hunter.adapters.cli.project import Project, stores_of
from hunter.adapters.cli.report import report_text
from hunter.adapters.cli.sources import sources_of
from hunter.adapters.matches import Matches
from hunter.application.discover import discover
from hunter.domain.discovery.campaign import Campaign


def run_discovery(project: Project, campaign_ids: Sequence[str], out: TextIO) -> int:
    try:
        campaigns = chosen(load_campaigns(project.campaigns_folder), campaign_ids)
    except (CampaignFileError, LookupError) as error:
        out.write(f"{error}\n")
        return 1
    database = project.database()
    sources = sources_of(project, database)
    reports = discover(sources, campaigns, stores_of(database), datetime.now(UTC))
    out.write(report_text(reports, campaigns, Matches(database)))
    return 0


def chosen(campaigns: Sequence[Campaign], ids: Sequence[str]) -> list[Campaign]:
    unknown = sorted(set(ids) - {campaign.id for campaign in campaigns})
    if unknown:
        raise LookupError(f"no campaign {', '.join(unknown)} in campaigns/")
    return [campaign for campaign in campaigns if not ids or campaign.id in ids]
