"""`python -m hunter.adapters.outcome`: the outcome metric from Hunter's run log, for
`doctrine metric record`.

The run log lives in var/ (gitignored, personal data), one JSON object per line:
- var/sessions.jsonl: {"started": ISO time, "ended": ISO time or null while running}
- var/submissions.jsonl: {"sent": ISO time, "proof": path under var/ or null}
A submission counts only when its proof file exists; a session still running doesn't count."""

import json
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from hunter.domain.outcome import Session, Submission, applications_per_hour

RUN_LOG = Path("var")


def records(path: Path) -> Iterator[dict[str, Any]]:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def sessions(folder: Path) -> list[Session]:
    return [
        Session(
            started=datetime.fromisoformat(record["started"]),
            ended=datetime.fromisoformat(record["ended"]),
        )
        for record in records(folder / "sessions.jsonl")
        if record.get("ended")
    ]


def submissions(folder: Path) -> list[Submission]:
    return [
        Submission(
            sent=datetime.fromisoformat(record["sent"]),
            proven=bool(record.get("proof")) and (folder / record["proof"]).is_file(),
        )
        for record in records(folder / "submissions.jsonl")
    ]


def outcome(root: Path) -> float:
    folder = root / RUN_LOG
    return applications_per_hour(sessions(folder), submissions(folder))


def main() -> None:
    sys.stdout.write(f"{outcome(Path.cwd()):.2f}\n")


if __name__ == "__main__":
    main()
