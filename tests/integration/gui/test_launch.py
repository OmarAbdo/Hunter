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
