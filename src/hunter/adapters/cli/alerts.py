"""The alert-mail sources a discovery run reads: the inboxes in var/accounts.toml, when that file
exists."""

from hunter.adapters.cli.project import Project
from hunter.adapters.credentials import accounts_from
from hunter.adapters.mail.mailbox import Mailbox
from hunter.adapters.sources.alerts.linkedin import LinkedInAlerts
from hunter.adapters.sources.alerts.stepstone import StepStoneAlerts
from hunter.adapters.sources.alerts.xing import XingAlerts
from hunter.adapters.sources.indeed_alerts import IndeedAlerts
from hunter.adapters.storage.mail_marks import MailMarks
from hunter.application.ports import JobSource


def alert_sources_of(project: Project) -> list[JobSource]:
    if not project.accounts_path.is_file():
        return []
    marks = MailMarks(project.database_path)
    inboxes = [Mailbox(account, marks) for account in accounts_from(project.accounts_path)]
    sources = (IndeedAlerts, LinkedInAlerts, StepStoneAlerts, XingAlerts)
    return [source(inboxes) for source in sources]
