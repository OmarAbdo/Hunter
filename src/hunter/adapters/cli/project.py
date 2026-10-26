"""Where a Hunter project keeps its files: campaigns/ (committed), and var/ for the database and
the credentials (personal, gitignored)."""

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from hunter.adapters.credentials import Keys, keys_from
from hunter.adapters.storage.database import open_database
from hunter.adapters.storage.job_links import JobLinks
from hunter.adapters.storage.matches import Matches
from hunter.adapters.storage.pool import Pool
from hunter.adapters.storage.registry import Registry
from hunter.application.discover import Stores
from hunter.application.resolve import resolve


@dataclass(frozen=True)
class Project:
    """`apis` replaces a source's web address, for tests; real runs leave it empty."""

    root: Path
    apis: Mapping[str, str] = field(default_factory=dict)

    @property
    def campaigns_folder(self) -> Path:
        return self.root / "campaigns"

    @property
    def accounts_path(self) -> Path:
        return self.root / "var" / "accounts.toml"

    @property
    def database_path(self) -> Path:
        return self.root / "var" / "hunter.db"

    def keys(self) -> Keys:
        """The keyed search sources' keys, from the credentials file."""
        return keys_from(self.accounts_path)

    def database(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(exist_ok=True)
        return open_database(self.database_path)


def stores_of(database: sqlite3.Connection) -> Stores:
    return Stores(jobs=Pool(database), companies=Registry(database), matches=Matches(database))


def linked_jobs(database: sqlite3.Connection) -> int:
    """Links job-board jobs to their employer's posting; how many it linked."""
    return resolve(JobLinks(database))
