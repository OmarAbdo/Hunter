"""`discover [--campaign ID]...`: reads every source for the chosen campaigns, all of them when none
is named. It prints a line for each source as soon as it's read, then the report. Ctrl+C stops the
run; everything read until then is kept."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TextIO

from hunter.adapters.campaign_files import CampaignFileError, load_campaigns
from hunter.adapters.cli.project import Project, stores_of
from hunter.adapters.cli.report import progress_line, report_text
from hunter.adapters.cli.sources import sources_of
from hunter.adapters.storage.matches import Matches
from hunter.application.discover import SourceReport, discover_each
from hunter.domain.discovery.campaign import Campaign

STOPPED = 130  # the exit status of a program stopped with Ctrl+C


def run_discovery(project: Project, campaign_ids: Sequence[str], out: TextIO) -> int:
    try:
        campaigns = chosen(load_campaigns(project.campaigns_folder), campaign_ids)
    except (CampaignFileError, LookupError) as error:
        out.write(f"{error}\n")
        return 1
    try:
        reports = read_sources(project, campaigns, out)
    except KeyboardInterrupt:
        out.write("Stopped. Everything read until now is kept.\n")
        return STOPPED
    out.write(report_text(reports, campaigns, Matches(project.database())))
    return 0


def read_sources(
    project: Project, campaigns: Sequence[Campaign], out: TextIO
) -> list[SourceReport]:
    database = project.database()
    sources = sources_of(project, database)
    names = ", ".join(campaign.id for campaign in campaigns)
    out.write(f"Reading {len(sources)} source{'' if len(sources) == 1 else 's'} for {names}\n")
    reports = []
    for report in discover_each(sources, campaigns, stores_of(database), datetime.now(UTC)):
        out.write(progress_line(report) + "\n")
        out.flush()
        reports.append(report)
    return reports


def chosen(campaigns: Sequence[Campaign], ids: Sequence[str]) -> list[Campaign]:
    unknown = sorted(set(ids) - {campaign.id for campaign in campaigns})
    if unknown:
        raise LookupError(f"no campaign {', '.join(unknown)} in campaigns/")
    return [campaign for campaign in campaigns if not ids or campaign.id in ids]
