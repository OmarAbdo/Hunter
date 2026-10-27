"""Which sources a discovery run reads: the feed of every board in the company registry, the
searches the campaigns name, and the alert mails in the inboxes when there are credentials for
them."""

import sqlite3

from hunter.adapters.cli.alerts import alert_sources_of
from hunter.adapters.cli.project import Project
from hunter.adapters.storage.holds import kept_pacing
from hunter.adapters.storage.registry import Registry
from hunter.adapters.sources.feed_table import APIS, FEEDS, PACE, PACES
from hunter.adapters.sources.searches.search_table import PACES as SEARCH_PACES, searches_of
from hunter.adapters.web_client import WebClient
from hunter.application.ports import JobSource
from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.campaign import Campaign


def sources_of(
    project: Project, database: sqlite3.Connection, campaigns: list[Campaign]
) -> list[JobSource]:
    """Raises LookupError for a search on a source Hunter doesn't know, or without its key."""
    web = WebClient(kept_pacing(SEARCH_PACES, PACE, project.database))
    searches = searches_of(web, campaigns, project.apis, project.keys())
    return [*feeds_of(project, database), *searches, *alert_sources_of(project)]


def feeds_of(project: Project, database: sqlite3.Connection) -> list[JobSource]:
    """One feed per board, even where two companies in the registry claim the same one."""
    web = WebClient(kept_pacing(PACES, PACE, project.database))
    apis = {**APIS, **project.apis}
    owners: dict[Board, str] = {}
    for company in Registry(database).all():
        for board in company.feeds_to_read():
            owners.setdefault(board, company.name)
    return [
        FEEDS[board.ats](web, board.slug, name, api=apis[board.ats])
        for board, name in owners.items()
        if board.ats in FEEDS
    ]
