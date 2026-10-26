from pathlib import Path

import pytest

from hunter.adapters.gui import desktop
from hunter.adapters.gui.desktop import LIMIT_SECONDS, Watch, make_shortcuts, shortcut_script

ROOT = Path("D:/1 Software/Projects/Hunter")


def test_the_icon_opens_hunter_without_a_console() -> None:
    script = shortcut_script(ROOT, Path("C:/Users/Someone/Desktop/Hunter.lnk"))
    assert "'C:\\Users\\Someone\\Desktop\\Hunter.lnk'" in script
    assert "'D:\\1 Software\\Projects\\Hunter\\.venv\\Scripts\\pythonw.exe'" in script
    assert "'\"D:\\1 Software\\Projects\\Hunter\\hunter-gui.pyw\"'" in script
    assert "WorkingDirectory = 'D:\\1 Software\\Projects\\Hunter'" in script


def test_a_quote_in_a_path_cannot_end_the_script_s_strings() -> None:
    script = shortcut_script(Path("D:/O'Brien/Hunter"), Path("C:/Desktop/Hunter.lnk"))
    assert "'D:\\O''Brien\\Hunter'" in script


def test_the_window_counts_as_open_while_it_keeps_saying_so() -> None:
    watch = Watch(started=0.0)
    watch.touch(10.0)
    assert not watch.closed(10.0 + LIMIT_SECONDS)
    assert watch.closed(10.0 + LIMIT_SECONDS + 1)


def test_a_window_that_never_opened_is_given_up_on_after_a_while() -> None:
    """Edge may take a moment to start, but not two minutes."""
    watch = Watch(started=0.0)
    assert not watch.closed(60.0)
    assert watch.closed(121.0)


def test_an_icon_is_made_on_the_desktop_and_in_the_start_menu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(desktop, "folders", lambda: [tmp_path / "Desktop", tmp_path / "Programs"])
    scripts: list[list[str]] = []
    made = make_shortcuts(ROOT, scripts.append)
    assert made == [tmp_path / "Desktop" / "Hunter.lnk", tmp_path / "Programs" / "Hunter.lnk"]
    assert [command[:3] for command in scripts] == [["powershell", "-NoProfile", "-Command"]] * 2
    assert "Hunter.lnk" in scripts[0][3]
