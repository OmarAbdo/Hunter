"""`discover [--campaign ID]...`: reads every source for the chosen campaigns, all of them when none
is named: the registry's boards, and the searches the chosen campaigns name. It prints a line for
each source as soon as it's read, then the report. Ctrl+C stops the run; everything read until
then is kept.

Each run's report is kept in the run log as it comes in, so it can be shown after the run; a run
that was stopped keeps the sources it read, and no end time."""

from collections.abc import Iterator, Sequence
from typing import TextIO

from hunter.adapters.campaign_files import CampaignFileError, load_campaigns
from hunter.adapters.cli.project import Project, linked_jobs, stores_of
from hunter.adapters.cli.report import progress_line, report_text
from hunter.adapters.cli.sources import sources_of
from hunter.adapters.storage.matches import Matches
from hunter.adapters.storage.run_log import DiscoveryRun, RunLog
from hunter.adapters.cli.parallel_reading import read_in_parallel
from hunter.application.discover import SourceReport, take_each
from hunter.application.ports import JobSource
from hunter.domain.discovery.campaign import Campaign

STOPPED = 130  # the exit status of a program stopped with Ctrl+C


def run_discovery(project: Project, campaign_ids: Sequence[str], out: TextIO) -> int:
    try:
        campaigns = chosen(load_campaigns(project.campaigns_folder), campaign_ids)
        sources = sources_of(project, project.database(), campaigns)
    except (CampaignFileError, LookupError) as error:
        out.write(f"{error}\n")
        return 1
    out.write(reading_line(sources, campaigns))
    runs = RunLog(project.database())
    run = runs.start([campaign.id for campaign in campaigns])
    reports = []
    try:
        for report in read_sources(project, sources, campaigns, run):
            runs.record(run.run_id, report)
            out.write(progress_line(report) + "\n")
            out.flush()
            reports.append(report)
    except KeyboardInterrupt:
        out.write("Stopped. Everything read until now is kept.\n")
        return STOPPED
    linked = linked_jobs(project.database())
    runs.finish(run.run_id, linked)
    out.write(f"{linked} job-board jobs linked to the employer's own posting\n")
    out.write(report_text(reports, campaigns, Matches(project.database())))
    return 0


def reading_line(sources: Sequence[JobSource], campaigns: Sequence[Campaign]) -> str:
    names = ", ".join(campaign.id for campaign in campaigns)
    return f"Reading {len(sources)} source{'' if len(sources) == 1 else 's'} for {names}\n"


def read_sources(
    project: Project, sources: Sequence[JobSource], campaigns: Sequence[Campaign], run: DiscoveryRun
) -> Iterator[SourceReport]:
    """Each source's report as soon as what it brought is taken in. Jobs are seen at the run's
    start."""
    stores = stores_of(project.database())
    return take_each(read_in_parallel(sources), campaigns, stores, run.started_at)


def chosen(campaigns: Sequence[Campaign], ids: Sequence[str]) -> list[Campaign]:
    unknown = sorted(set(ids) - {campaign.id for campaign in campaigns})
    if unknown:
        raise LookupError(f"no campaign {', '.join(unknown)} in campaigns/")
    return [campaign for campaign in campaigns if not ids or campaign.id in ids]
