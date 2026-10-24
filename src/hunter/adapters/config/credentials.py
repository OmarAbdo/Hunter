"""Hunter's credentials: var/accounts.toml, personal and gitignored. Never commit or print them."""

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MailAccount:
    address: str
    app_password: str
    host: str = "imap.gmail.com"


def accounts_from(path: Path) -> list[MailAccount]:
    settings = tomllib.loads(path.read_text(encoding="utf-8"))
    return [MailAccount(**entry) for entry in settings["mailbox"]]
