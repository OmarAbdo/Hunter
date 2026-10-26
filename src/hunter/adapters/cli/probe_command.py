"""`boards probe [--limit N]`: looks for the boards of companies known only by name, several at a
time, and prints a line for each as soon as it's done. A board found joins the registry, so the
company's jobs come from its own system from the next discovery run on."""

from datetime import UTC, datetime, timedelta
from typing import TextIO

from hunter.adapters.cli.parallel_reading import in_parallel
from hunter.adapters.cli.probe_targets import companies_to_probe
from hunter.adapters.cli.project import Project
from hunter.adapters.sources.feed_table import APIS, PACES
from hunter.adapters.sources.feeds import board_check, careers_pages
from hunter.adapters.storage.probe_log import ProbeLog
from hunter.adapters.storage.registry import Registry
from hunter.adapters.web_client import WebClient
from hunter.application.probe import ProbeResult, ProbeStores, find_board, kept
from hunter.domain.pacing import Pacing, PaceRule

PACE = PaceRule(min_gap=timedelta(seconds=1))
STOPPED = 130  # the exit status of a program stopped with Ctrl+C


def run_probe(project: Project, limit: int, out: TextIO) -> int:
    database = project.database()
    companies = companies_to_probe(project, database, limit)
    out.write(
        f"Probing {len(companies)} compan{'y' if len(companies) == 1 else 'ies'} for their boards\n"
    )
    web = WebClient(Pacing(PACES, default=PACE))
    check = board_check.FeedCheck(web, {**APIS, **project.apis})
    pages = careers_pages.CareersPages(web)
    stores = ProbeStores(companies=Registry(database), log=ProbeLog(database))
    now = datetime.now(UTC)
    found = 0
    try:
        for company, finding in in_parallel(
            lambda company: find_board(company, check, pages), companies
        ):
            result = kept(company, finding, stores, now)
            found += result.board is not None
            out.write(result_line(result) + "\n")
            out.flush()
    except KeyboardInterrupt:
        out.write("Stopped. Every company probed until now is kept.\n")
        return STOPPED
    out.write(f"{found} of {len(companies)} found a board\n")
    return 0


def result_line(result: ProbeResult) -> str:
    if result.error:
        return f"  {result.company}: couldn't tell ({result.error})"
    return f"  {result.company}: {result.board.key if result.board else 'no board'}"
