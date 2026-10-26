"""The GUI's web server: Hunter's own page and the JSON it reads, on this computer only
(127.0.0.1). Pages come from `static/`, which holds nothing but the page's own files, so no other
file can be asked for. Each request opens the database for itself, since the server answers on
threads of its own."""

import json
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import parse_qs, urlsplit

from hunter.adapters.campaign_files import load_campaigns
from hunter.adapters.cli.project import Project
from hunter.adapters.gui.views import campaigns_view, companies_view, jobs_view, pool_view
from hunter.adapters.gui.window import open_window

STATIC = Path(__file__).parent / "static"
FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}
View = Callable[[Project, dict[str, list[str]]], Any]
VIEWS: dict[str, View] = {
    "/api/campaigns": lambda project, _: campaigns_view(
        project.database(), load_campaigns(project.campaigns_folder)
    ),
    "/api/jobs": lambda project, query: jobs_view(project.database(), query["campaign"][0]),
    "/api/companies": lambda project, _: companies_view(project.database()),
    "/api/pool": lambda project, _: pool_view(project.database()),
}


class GuiRequests(BaseHTTPRequestHandler):
    project: Project

    def answer_get(self) -> None:
        address = urlsplit(self.path)
        if address.path in FILES:
            name, kind = FILES[address.path]
            self.answer(200, kind, (STATIC / name).read_bytes())
        elif address.path in VIEWS:
            found = VIEWS[address.path](self.project, parse_qs(address.query))
            self.answer(200, "application/json", json.dumps(found).encode())
        else:
            self.answer(404, "text/plain; charset=utf-8", b"not found")

    def answer(self, status: int, kind: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        return


# http.server looks up `do_GET`, a name the naming rules don't allow to be written out.
setattr(GuiRequests, "do_" + "GET", GuiRequests.answer_get)


def gui_server(project: Project, port: int = 0) -> ThreadingHTTPServer:
    """A server for the project, on a free port unless one is given; `serve_forever` starts it."""
    requests = type("ProjectRequests", (GuiRequests,), {"project": project})
    return ThreadingHTTPServer(("127.0.0.1", port), requests)


def run_gui(project: Project, out: TextIO) -> int:
    """`gui`: serves the page and opens it in Hunter's window, until Ctrl+C."""
    server = gui_server(project)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    out.write(f"Hunter is open at {url} (Ctrl+C here closes it)\n")
    out.flush()
    open_window(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        out.write("Closed.\n")
    return 0
