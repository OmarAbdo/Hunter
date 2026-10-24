"""Which sources a discovery run reads: the feed of every board in the company registry, and the
alert mails in the inboxes when there are credentials for them."""

import sqlite3
from datetime import timedelta

from hunter.adapters.cli.alerts import alert_sources_of
from hunter.adapters.cli.project import Project
from hunter.adapters.storage.registry import Registry
from hunter.adapters.sources.feed_table import APIS, FEEDS
from hunter.adapters.web_client import WebClient
from hunter.application.ports import JobSource
from hunter.domain.discovery.boards import Board
from hunter.domain.pacing import Pacing, PaceRule

PACE = PaceRule(min_gap=timedelta(seconds=1))


def sources_of(project: Project, database: sqlite3.Connection) -> list[JobSource]:
    return [*feeds_of(project, database), *alert_sources_of(project)]


def feeds_of(project: Project, database: sqlite3.Connection) -> list[JobSource]:
    """One feed per board, even where two companies in the registry claim the same one."""
    web = WebClient(Pacing({}, default=PACE))
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
