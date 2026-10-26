"""Hunter's window: its page in an Edge app window (no tabs, no address bar, a window of its own),
which every Windows has; the usual browser where Edge isn't found."""

import subprocess
import webbrowser
from collections.abc import Callable, Sequence
from pathlib import Path

EDGE = (
    Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
)


def open_window(
    url: str,
    edges: Sequence[Path] = EDGE,
    start: Callable[[list[str]], object] = subprocess.Popen,
    browse: Callable[[str], object] = webbrowser.open,
) -> None:
    edge = next((path for path in edges if path.is_file()), None)
    if edge:
        start([str(edge), f"--app={url}"])
    else:
        browse(url)
