import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hunter.adapters.outcome import outcome

HOUR = "2026-10-23T{:02d}:00:00+00:00"
SOURCE = Path(__file__).resolve().parents[2] / "src"


def write_lines(path: Path, records: list[dict[str, str | None]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


def proof(root: Path, name: str) -> str:
    path = root / "var" / "proof" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("confirmation", encoding="utf-8")
    return f"proof/{name}"


def run_log(root: Path, submissions: list[dict[str, str | None]]) -> None:
    write_lines(
        root / "var" / "sessions.jsonl",
        [{"started": HOUR.format(9), "ended": HOUR.format(12)}],
    )
    write_lines(root / "var" / "submissions.jsonl", submissions)


def test_no_run_log_is_zero(tmp_path: Path) -> None:
    assert outcome(tmp_path) == 0


def test_counts_submissions_whose_proof_exists(tmp_path: Path) -> None:
    run_log(
        tmp_path,
        [
            {"sent": HOUR.format(10), "proof": proof(tmp_path, "first.png")},
            {"sent": HOUR.format(11), "proof": proof(tmp_path, "second.png")},
            {"sent": HOUR.format(11), "proof": "proof/missing.png"},
            {"sent": HOUR.format(11), "proof": None},
        ],
    )
    assert outcome(tmp_path) == pytest.approx(2 / 3)


def test_a_session_still_running_does_not_count(tmp_path: Path) -> None:
    write_lines(tmp_path / "var" / "sessions.jsonl", [{"started": HOUR.format(9), "ended": None}])
    write_lines(
        tmp_path / "var" / "submissions.jsonl",
        [{"sent": HOUR.format(10), "proof": proof(tmp_path, "first.png")}],
    )
    assert outcome(tmp_path) == 0


def test_the_command_prints_the_number(tmp_path: Path) -> None:
    run_log(tmp_path, [{"sent": HOUR.format(10), "proof": proof(tmp_path, "first.png")}])
    finished = subprocess.run(
        [sys.executable, "-m", "hunter.adapters.outcome"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(SOURCE)},
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert finished.stdout.strip().splitlines()[-1] == "0.33"
