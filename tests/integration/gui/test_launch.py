import io
import shutil
from pathlib import Path

import pytest

from hunter.adapters.cli.project import Project
from hunter.adapters.gui import desktop, launch

REPOSITORY = Path(__file__).resolve().parents[3]


def test_hunter_stops_once_its_window_never_opened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shutil.copytree(REPOSITORY / "campaigns", tmp_path / "campaigns")
    opened: list[str] = []
    monkeypatch.setattr(launch, "open_window", opened.append)
    monkeypatch.setattr(desktop, "FIRST_OPEN_SECONDS", 0.2)
    monkeypatch.setattr(launch, "WATCH_STEP_SECONDS", 0.05)
    out = io.StringIO()
    assert launch.run_gui(Project(tmp_path), out) == 0
    [url] = opened
    assert url.startswith("http://127.0.0.1:")
    assert out.getvalue().splitlines() == [
        f"Hunter is open at {url} (closing its window, or Ctrl+C here, stops it)",
        "Closed.",
    ]


class Reading:
    def __init__(self, reading: bool) -> None:
        self.is_reading = reading

    def reading(self) -> bool:
        return self.is_reading


def test_hunter_stays_while_a_run_is_reading_even_with_its_window_closed() -> None:
    """Closing the window doesn't end a run halfway; a paused run isn't waited for."""
    closed = desktop.Watch(started=0.0)
    closed.touch(0.0)
    late = desktop.LIMIT_SECONDS + 1
    assert not launch.should_close(closed, Reading(reading=True), late)
    assert launch.should_close(closed, Reading(reading=False), late)
    assert not launch.should_close(closed, Reading(reading=False), 1.0)


def test_without_a_console_what_hunter_says_goes_to_its_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The icons start Hunter with pythonw, which has no console: there's no sys.stdout to write to,
    so writing to it ended Hunter before its window opened."""
    said: list[str] = []

    def gui(project: Project, out: object) -> int:
        print("Hunter is open", file=out)
        said.append(str(project.root))
        raise RuntimeError("broken")

    monkeypatch.setattr(launch, "run_gui", gui)
    monkeypatch.setattr("sys.stdout", None)
    monkeypatch.setattr("sys.stderr", None)
    with pytest.raises(RuntimeError):
        launch.without_console(tmp_path)
    log = (tmp_path / "var" / "hunter-gui.log").read_text(encoding="utf-8")
    assert said == [str(tmp_path)]
    assert "Hunter is open" in log
    assert "RuntimeError: broken" in log
