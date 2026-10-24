"""The report a discovery run prints: what each source brought, what each campaign took, and why
the campaigns turned the other jobs down."""

from collections.abc import Sequence

from hunter.adapters.storage.matches import Matches
from hunter.application.discover import SourceReport
from hunter.domain.discovery.campaign import Campaign


def report_text(
    reports: Sequence[SourceReport], campaigns: Sequence[Campaign], matches: Matches
) -> str:
    ids = [campaign.id for campaign in campaigns]
    rows = [["source", "fetched", "new", *ids]]
    rows += [[report.source, *counts(report, ids)] for report in reports]
    rows.append(["total", *totals(reports, ids)])
    lines = table(rows)
    lines += [f"{report.source}: {report.error}" for report in reports if report.error]
    lines += [turned_down(campaign_id, matches) for campaign_id in ids]
    return "\n".join(lines) + "\n"


def progress_line(report: SourceReport) -> str:
    """One source, as soon as it's read."""
    if report.error:
        return f"  {report.source}: failed ({report.error})"
    taken = sum(report.taken.values())
    return f"  {report.source}: {report.fetched} fetched, {report.new_jobs} new, {taken} taken"


def counts(report: SourceReport, ids: Sequence[str]) -> list[str]:
    taken = [report.taken.get(campaign_id, 0) for campaign_id in ids]
    return [str(number) for number in (report.fetched, report.new_jobs, *taken)]


def totals(reports: Sequence[SourceReport], ids: Sequence[str]) -> list[str]:
    columns = zip(*(map(int, counts(report, ids)) for report in reports), strict=True)
    return [str(sum(column)) for column in columns] if reports else ["0"] * (2 + len(ids))


def turned_down(campaign_id: str, matches: Matches) -> str:
    """Every job the campaign ever turned down, by reason, most common first."""
    reasons = sorted(matches.rejections(campaign_id).items(), key=lambda item: -item[1])
    summary = ", ".join(f"{reason.value} {count}" for reason, count in reasons) or "nothing"
    return f"{campaign_id} turned down: {summary}"


def table(rows: list[list[str]]) -> list[str]:
    """The first column left-aligned, the numbers right-aligned."""
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return [
        "  ".join(
            cell.ljust(width) if column == 0 else cell.rjust(width)
            for column, (cell, width) in enumerate(zip(row, widths, strict=True))
        )
        for row in rows
    ]
