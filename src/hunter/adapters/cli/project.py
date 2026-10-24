"""Where a Hunter project keeps its files: campaigns/ (committed), and var/ for the database and
the credentials (personal, gitignored)."""

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from hunter.adapters.database import open_database
from hunter.adapters.matches import Matches
from hunter.adapters.pool import Pool
from hunter.adapters.registry import Registry
from hunter.application.discover import Stores


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

    def database(self) -> sqlite3.Connection:
        (self.root / "var").mkdir(exist_ok=True)
        return open_database(self.root / "var" / "hunter.db")


def stores_of(database: sqlite3.Connection) -> Stores:
    return Stores(jobs=Pool(database), companies=Registry(database), matches=Matches(database))
