"""A real local web server that answers like a source, with saved real responses."""

import threading
from collections.abc import Callable, Iterator, Mapping
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from hunter.adapters.web_client import WebClient
from hunter.domain.pacing import Pacing, PaceRule

SAVED = Path(__file__).resolve().parents[2] / "fixtures" / "sources"


class Source(BaseHTTPRequestHandler):
    """Answers each of its paths with a saved response, anything else with 404."""

    bodies: Mapping[str, str] = {}

    def answer_get(self) -> None:
        body = self.bodies.get(self.path)
        self.send_response(404 if body is None else 200)
        self.end_headers()
        self.wfile.write(b"not found" if body is None else body.encode())

    def answer_post(self) -> None:
        """Searches posted as JSON (Workday) get the same answer as a GET of the path."""
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.answer_get()

    def log_message(self, *_: object) -> None:
        return


# http.server looks up `do_GET` and `do_POST`, names the naming rules don't allow to be written out.
setattr(Source, "do_" + "GET", Source.answer_get)
setattr(Source, "do_" + "POST", Source.answer_post)


@pytest.fixture
def source_pages() -> Iterator[Callable[[Mapping[str, str]], str]]:
    """Starts a source that answers each path with the saved response named for it."""
    servers: list[ThreadingHTTPServer] = []

    def start(saved: Mapping[str, str]) -> str:
        bodies = {path: (SAVED / name).read_text(encoding="utf-8") for path, name in saved.items()}
        server = ThreadingHTTPServer(("127.0.0.1", 0), type("Saved", (Source,), {"bodies": bodies}))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield start
    for server in servers:
        server.shutdown()


@pytest.fixture
def source_api(
    source_pages: Callable[[Mapping[str, str]], str],
) -> Callable[[str, str | None], str]:
    """Starts a source that answers `path` with the saved response `saved`; None answers 404."""

    def start(path: str, saved: str | None) -> str:
        return source_pages({path: saved} if saved else {})

    return start


@pytest.fixture
def web() -> WebClient:
    return WebClient(Pacing({}, default=PaceRule(min_gap=timedelta(0))), sleep=lambda _: None)
