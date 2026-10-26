"""The GUI's web server: Hunter's own page and the JSON it reads, on this computer only
(127.0.0.1). Pages come from `static/`, which holds nothing but the page's own files, so no other
file can be asked for. Each request opens the database for itself, since the server answers on
threads of its own. A discovery run started from the page runs on a thread of the server's."""

import json
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from hunter.adapters.campaign_files import load_campaigns
from hunter.adapters.cli.project import Project
from hunter.adapters.gui.desktop import Watch
from hunter.adapters.gui.runner import LiveRun
from hunter.adapters.gui import views

STATIC = Path(__file__).parent / "static"
FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


class GuiRequests(BaseHTTPRequestHandler):
    project: Project
    watch: Watch
    live: LiveRun

    def answer_get(self) -> None:
        address = urlsplit(self.path)
        if address.path in FILES:
            name, kind = FILES[address.path]
            self.answer(200, kind, (STATIC / name).read_bytes())
        elif address.path in VIEWS:
            found = VIEWS[address.path](self, parse_qs(address.query))
            self.answer(200, "application/json", json.dumps(found).encode())
        else:
            self.answer(404, "text/plain; charset=utf-8", b"not found")

    def answer_post(self) -> None:
        """`/api/runs` starts a discovery run: 202 when it started, 409 when one is going."""
        if urlsplit(self.path).path != "/api/runs":
            self.answer(404, "text/plain; charset=utf-8", b"not found")
            return
        started = self.live.start()
        self.answer(202 if started else 409, "application/json", json.dumps(started).encode())

    def alive(self) -> bool:
        """The page saying it's still open."""
        self.watch.touch(time.monotonic())
        return True

    def answer(self, status: int, kind: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        return


View = Callable[[GuiRequests, dict[str, list[str]]], Any]
VIEWS: dict[str, View] = {
    "/api/alive": lambda requests, _: requests.alive(),
    "/api/campaigns": lambda requests, _: views.campaigns_view(
        requests.project.database(), load_campaigns(requests.project.campaigns_folder)
    ),
    "/api/jobs": lambda requests, query: views.jobs_view(
        requests.project.database(), query["campaign"][0]
    ),
    "/api/companies": lambda requests, _: views.companies_view(requests.project.database()),
    "/api/pool": lambda requests, _: views.pool_view(requests.project.database()),
    "/api/runs": lambda requests, _: views.runs_view(requests.project.database()),
    "/api/runs/live": lambda requests, _: requests.live.state(),
}

# http.server looks up `do_GET` and `do_POST`, names the naming rules don't allow to be written out.
setattr(GuiRequests, "do_" + "GET", GuiRequests.answer_get)
setattr(GuiRequests, "do_" + "POST", GuiRequests.answer_post)


def gui_server(project: Project, watch: Watch | None = None) -> ThreadingHTTPServer:
    """A server for the project on a free port; `serve_forever` starts it."""
    seen = watch or Watch(started=time.monotonic())
    attributes = {"project": project, "watch": seen, "live": LiveRun(project)}
    requests = type("ProjectRequests", (GuiRequests,), attributes)
    return ThreadingHTTPServer(("127.0.0.1", 0), requests)
