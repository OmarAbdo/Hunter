"""`gui`: Hunter's window. It serves the page, opens the window, and stops once the window has
been closed for a while, or at Ctrl+C in a console."""

import threading
import time
from typing import TextIO

from hunter.adapters.cli.project import Project
from hunter.adapters.gui.desktop import Watch
from hunter.adapters.gui.server import gui_server
from hunter.adapters.gui.window import open_window

WATCH_STEP_SECONDS = 2.0


def run_gui(project: Project, out: TextIO) -> int:
    """`gui`: serves the page and opens it in Hunter's window, until the window is closed (or
    Ctrl+C in a console)."""
    watch = Watch(started=time.monotonic())
    server = gui_server(project, watch)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    out.write(f"Hunter is open at {url} (closing its window, or Ctrl+C here, stops it)\n")
    out.flush()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    open_window(url)
    try:
        while not watch.closed(time.monotonic()):
            time.sleep(WATCH_STEP_SECONDS)
    except KeyboardInterrupt:
        pass
    server.shutdown()
    out.write("Closed.\n")
    return 0
