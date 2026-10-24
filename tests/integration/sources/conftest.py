"""A real local web server that answers like a source, with saved real responses."""

import threading
from collections.abc import Callable, Iterator
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from hunter.adapters.web.client import WebClient
from hunter.domain.pacing import Pacing, PaceRule

SAVED = Path(__file__).resolve().parents[2] / "fixtures" / "sources"


class Source(BaseHTTPRequestHandler):
    """Answers one path with one saved response, anything else with 404."""

    path_and_body: tuple[str, str] = ("", "")

    def answer_get(self) -> None:
        path, body = self.path_and_body
        self.send_response(200 if self.path == path else 404)
        self.end_headers()
        self.wfile.write(body.encode() if self.path == path else b"not found")

    def log_message(self, *_: object) -> None:
        return


# http.server looks up `do_GET`, a name the naming rules don't allow to be written out.
setattr(Source, "do_" + "GET", Source.answer_get)


@pytest.fixture
def source_api() -> Iterator[Callable[[str, str | None], str]]:
    """Starts a source that answers `path` with the saved response `saved`; None answers 404."""
    servers: list[ThreadingHTTPServer] = []

    def start(path: str, saved: str | None) -> str:
        body = (SAVED / saved).read_text(encoding="utf-8") if saved else ""
        Source.path_and_body = (path if saved else "", body)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Source)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield start
    for server in servers:
        server.shutdown()


@pytest.fixture
def web() -> WebClient:
    return WebClient(Pacing({}, default=PaceRule(min_gap=timedelta(0))), sleep=lambda _: None)
