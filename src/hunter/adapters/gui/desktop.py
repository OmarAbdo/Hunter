"""Hunter as a program on the desktop: an icon on the desktop and in the Start menu that opens its
window without a console, and a server that closes itself once its window is gone. The page says
it's open every few seconds; when it stops saying so, nobody is looking anymore."""

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

LIMIT_SECONDS = 30.0  # the page says it's open every 5 seconds
FIRST_OPEN_SECONDS = 120.0  # how long Edge may take to show the page at all
ICON = "%SystemRoot%\\System32\\imageres.dll,-5323"  # Windows' own magnifying glass


@dataclass
class Watch:
    """Whether Hunter's window is still open, by when the page last said so (monotonic seconds)."""

    started: float
    last_seen: float | None = field(default=None)

    def touch(self, now: float) -> None:
        self.last_seen = now

    def closed(self, now: float) -> bool:
        if self.last_seen is None:
            return now - self.started > FIRST_OPEN_SECONDS
        return now - self.last_seen > LIMIT_SECONDS


def quoted(text: str) -> str:
    """A PowerShell string in single quotes, where nothing is special but a doubled quote."""
    return "'" + text.replace("'", "''") + "'"


def shortcut_script(project: Path, shortcut_path: Path) -> str:
    """PowerShell that makes the shortcut open Hunter's window from the project. The paths are
    written the Windows way, wherever this runs."""
    root, shortcut = PureWindowsPath(project), PureWindowsPath(shortcut_path)
    target = root / ".venv" / "Scripts" / "pythonw.exe"
    launcher = f'"{root / "hunter-gui.pyw"}"'
    shell = "(New-Object -ComObject WScript.Shell)"
    return "; ".join(
        [
            f"$link = {shell}.CreateShortcut({quoted(str(shortcut))})",
            f"$link.TargetPath = {quoted(str(target))}",
            f"$link.Arguments = {quoted(launcher)}",
            f"$link.WorkingDirectory = {quoted(str(root))}",
            f"$link.IconLocation = {quoted(ICON)}",
            "$link.Description = 'Hunter: find jobs and apply'",
            "$link.Save()",
        ]
    )


def folders() -> list[Path]:
    """The desktop and the Start menu's programs, as Windows names them for this user."""
    names = "[Environment]::GetFolderPath('Desktop'); [Environment]::GetFolderPath('Programs')"
    found = subprocess.run(
        ["powershell", "-NoProfile", "-Command", names], capture_output=True, text=True, check=True
    )
    return [Path(line) for line in found.stdout.splitlines() if line.strip()]


def make_shortcuts(root: Path, run: Callable[[list[str]], object] = subprocess.run) -> list[Path]:
    made = [folder / "Hunter.lnk" for folder in folders()]
    for shortcut in made:
        run(["powershell", "-NoProfile", "-Command", shortcut_script(root, shortcut)])
    return made
