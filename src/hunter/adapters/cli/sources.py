"""Which sources a discovery run reads: the feed of every board in the company registry, and the
alert mails in the inboxes when there are credentials for them."""

import sqlite3
from datetime import timedelta

from hunter.adapters.cli.project import Project
from hunter.adapters.credentials import accounts_from
from hunter.adapters.mail.mailbox import Mailbox
from hunter.adapters.storage.mail_marks import MailMarks
from hunter.adapters.storage.registry import Registry
from hunter.adapters.sources.feed_table import APIS, FEEDS
from hunter.adapters.sources.indeed_alerts import IndeedAlerts
from hunter.adapters.web_client import WebClient
from hunter.application.ports import JobSource
from hunter.domain.pacing import Pacing, PaceRule

PACE = PaceRule(min_gap=timedelta(seconds=1))


def sources_of(project: Project, database: sqlite3.Connection) -> list[JobSource]:
    return [*feeds_of(project, database), *alert_sources_of(project)]


def feeds_of(project: Project, database: sqlite3.Connection) -> list[JobSource]:
    web = WebClient(Pacing({}, default=PACE))
    apis = {**APIS, **project.apis}
    return [
        FEEDS[board.ats](web, board.slug, company.name, api=apis[board.ats])
        for company in Registry(database).all()
        for board in company.feeds_to_read()
        if board.ats in FEEDS
    ]


def alert_sources_of(project: Project) -> list[JobSource]:
    if not project.accounts_path.is_file():
        return []
    marks = MailMarks(project.database_path)
    inboxes = [Mailbox(account, marks) for account in accounts_from(project.accounts_path)]
    return [IndeedAlerts(inboxes)]
