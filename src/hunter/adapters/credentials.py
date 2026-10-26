"""Hunter's credentials: var/accounts.toml, personal and gitignored. Never commit or print them."""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MailAccount:
    address: str
    app_password: str
    host: str = "imap.gmail.com"


def accounts_from(path: Path) -> list[MailAccount]:
    settings = tomllib.loads(path.read_text(encoding="utf-8"))
    return [MailAccount(**entry) for entry in settings["mailbox"]]


Keys = dict[str, dict[str, Any]]  # each keyed source's settings, by source


def keys_from(path: Path) -> Keys:
    """The API keys of the keyed search sources, by source: `[keys.<source>]` tables."""
    if not path.is_file():
        return {}
    keys: Keys = tomllib.loads(path.read_text(encoding="utf-8")).get("keys", {})
    return keys
