from datetime import UTC, datetime
from pathlib import Path

from hunter.adapters.storage.database import open_database
from hunter.adapters.storage.probe_log import ProbeLog

PROBED = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)


def test_probed_companies_are_remembered(tmp_path: Path) -> None:
    log = ProbeLog(open_database(tmp_path / "hunter.db"))
    log.record("n26", PROBED)
    assert log.probed() == {"n26"}


def test_probing_again_keeps_one_entry(tmp_path: Path) -> None:
    log = ProbeLog(open_database(tmp_path / "hunter.db"))
    log.record("n26", PROBED)
    log.record("n26", PROBED)
    assert log.probed() == {"n26"}


def test_the_log_survives_a_restart(tmp_path: Path) -> None:
    ProbeLog(open_database(tmp_path / "hunter.db")).record("n26", PROBED)
    assert ProbeLog(open_database(tmp_path / "hunter.db")).probed() == {"n26"}
