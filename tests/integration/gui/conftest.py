"""A Hunter project with a small pilot campaign (one search), whose every source answers from a
local site that has nothing (404), so a whole discovery run takes a moment and reaches no real
site."""

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from hunter.adapters.cli.project import Project
from hunter.adapters.sources.feed_table import APIS as FEED_APIS
from hunter.adapters.sources.searches.search_table import APIS as SEARCH_APIS

PILOT = """
title = "Full-time software jobs in Berlin"
home = "DE"
countries = ["DE"]
cities = ["Berlin"]

[[searches]]
source = "bundesagentur"
query = "Softwareentwickler"
place = "Berlin"
"""


class Nothing(BaseHTTPRequestHandler):
    def answer(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(404)
        self.end_headers()

    def log_message(self, *_: object) -> None:
        return


# http.server looks up `do_GET` and `do_POST`, names the naming rules don't allow to be written out.
setattr(Nothing, "do_" + "GET", Nothing.answer)
setattr(Nothing, "do_" + "POST", Nothing.answer)


@pytest.fixture
def quiet_project(tmp_path: Path) -> Iterator[Project]:
    (tmp_path / "campaigns").mkdir()
    (tmp_path / "campaigns" / "de-swe-berlin.toml").write_text(PILOT, encoding="utf-8")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Nothing)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    nowhere = f"http://127.0.0.1:{server.server_address[1]}"
    yield Project(tmp_path, dict.fromkeys([*FEED_APIS, *SEARCH_APIS], nowhere))
    server.shutdown()
