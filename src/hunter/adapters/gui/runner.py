"""A discovery run started from Hunter's window: the same run as `hunter discover`, on a thread of
its own, its lines kept as they're printed so the page can follow them. One run at a time; the
lines of the last run stay until the next one starts."""

import io
import threading
from typing import Any

from hunter.adapters.cli.discover_command import run_discovery
from hunter.adapters.cli.project import Project


class Lines(io.StringIO):
    """What a run prints, kept line by line for another thread to read."""

    def __init__(self) -> None:
        super().__init__()
        self.lock = threading.Lock()
        self.lines: list[str] = []

    def write(self, text: str) -> int:
        with self.lock:
            self.lines.extend(line for line in text.splitlines() if line.strip())
        return len(text)

    def copy(self) -> list[str]:
        with self.lock:
            return list(self.lines)


class LiveRun:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None
        self.lines = Lines()

    def start(self) -> bool:
        """Starts a run for every campaign; False when one is still going."""
        with self.lock:
            if self.thread and self.thread.is_alive():
                return False
            self.lines = Lines()
            self.thread = threading.Thread(target=self._run, args=(self.lines,), daemon=True)
            self.thread.start()
            return True

    def state(self) -> dict[str, Any]:
        with self.lock:
            running = bool(self.thread and self.thread.is_alive())
            return {"running": running, "lines": self.lines.copy()}

    def _run(self, lines: Lines) -> None:
        run_discovery(self.project, [], lines)
