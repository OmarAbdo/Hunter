"""A discovery run started from Hunter's window: the same run as `hunter discover`, on a thread of
its own, its lines kept as they're printed so the page can follow them. One run at a time; the
lines of the last run stay until the next one starts. A run can be paused, resumed and stopped."""

import io
import threading
from collections.abc import Callable
from typing import Any, TextIO

from hunter.adapters.cli.discover_command import run_discovery
from hunter.adapters.cli.parallel_reading import RunControl
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


Discover = Callable[[Project, list[str], TextIO, RunControl], int]


class LiveRun:
    """`discover` is the run itself; tests give a stand-in."""

    def __init__(self, project: Project, discover: Discover = run_discovery) -> None:
        self.project = project
        self.discover = discover
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None
        self.lines = Lines()
        self.control = RunControl()

    def start(self) -> bool:
        """Starts a run for every campaign; False when one is still going."""
        with self.lock:
            if self._running():
                return False
            self.lines, self.control = Lines(), RunControl()
            arguments: tuple[Project, list[str], TextIO, RunControl] = (
                self.project,
                [],
                self.lines,
                self.control,
            )
            self.thread = threading.Thread(target=self.discover, args=arguments, daemon=True)
            self.thread.start()
            return True

    def pause(self) -> bool:
        """Sources not started yet wait; False when there's no run to pause."""
        return self._act(self.control.pause)

    def resume(self) -> bool:
        return self._act(self.control.resume)

    def stop(self) -> bool:
        """No source not started yet is read; those being read finish and are kept."""
        return self._act(self.control.stop)

    def reading(self) -> bool:
        """Whether a run is going on and isn't paused."""
        with self.lock:
            return self._running() and not self.control.paused

    def state(self) -> dict[str, Any]:
        with self.lock:
            running = self._running()
            return {
                "running": running,
                "paused": running and self.control.paused,
                "stopping": running and self.control.stopped,
                "lines": self.lines.copy(),
            }

    def _act(self, action: Callable[[], None]) -> bool:
        with self.lock:
            if not self._running():
                return False
            action()
            return True

    def _running(self) -> bool:
        return bool(self.thread and self.thread.is_alive())
