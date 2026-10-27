"""The pauses sites asked Hunter for (docs/sources.md), kept so a pause longer than a run holds
for the next runs too: until it ends, a site isn't asked again, whichever run or command asks."""

import sqlite3
from collections.abc import Callable, Mapping
from contextlib import closing
from datetime import UTC, datetime

from hunter.domain.pacing import Pacing, PaceRule


class Holds:
    def __init__(self, database: sqlite3.Connection) -> None:
        self.database = database

    def save(self, host: str, until: datetime) -> None:
        """Keeps a host's pause; of two pauses for one host, the one that ends later."""
        with self.database:
            self.database.execute(
                "INSERT INTO holds (host, until) VALUES (?, ?) ON CONFLICT (host) "
                "DO UPDATE SET until = max(until, excluded.until)",
                (host, until.astimezone(UTC).isoformat()),
            )

    def current(self, now: datetime) -> dict[str, datetime]:
        """The pauses that haven't ended at `now`."""
        rows = self.database.execute("SELECT host, until FROM holds").fetchall()
        held = {host: datetime.fromisoformat(until) for host, until in rows}
        return {host: until for host, until in held.items() if until > now}


def kept_pacing(
    rules: Mapping[str, PaceRule], default: PaceRule, connect: Callable[[], sqlite3.Connection]
) -> Pacing:
    """A pacing that starts from the pauses still on, and keeps each pause a site asks for as soon
    as it's asked, so a run that's stopped or crashes keeps it too. A pause is asked for on a
    reading thread, so each is saved on a connection of its own."""

    def keep(host: str, until: datetime) -> None:
        with closing(connect()) as database:
            Holds(database).save(host, until)

    with closing(connect()) as database:
        held = Holds(database).current(datetime.now(UTC))
    return Pacing(rules, default, held, keep)
