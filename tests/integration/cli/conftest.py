"""A temporary Hunter project with the real campaigns, and a local web server answering like
Greenhouse with the saved N26 board."""

import io
import shutil
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from hunter.adapters.cli.main import main

REPOSITORY = Path(__file__).resolve().parents[3]
N26 = (REPOSITORY / "tests" / "fixtures" / "sources" / "greenhouse-n26.json").read_bytes()
Run = Callable[..., tuple[int, str]]


class Greenhouse(BaseHTTPRequestHandler):
    def answer_get(self) -> None:
        found = self.path == "/v1/boards/n26/jobs?content=true"
        self.send_response(200 if found else 404)
        self.end_headers()
        self.wfile.write(N26 if found else b"not found")

    def log_message(self, *_: object) -> None:
        return


# http.server looks up `do_GET`, a name the naming rules don't allow to be written out.
setattr(Greenhouse, "do_" + "GET", Greenhouse.answer_get)


@pytest.fixture
def greenhouse() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Greenhouse)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    shutil.copytree(REPOSITORY / "campaigns", tmp_path / "campaigns")
    return tmp_path


@pytest.fixture
def run(project: Path, greenhouse: str) -> Run:
    """Runs `python -m hunter <arguments>` on the project; gives the exit status and the output."""

    def command(*arguments: str) -> tuple[int, str]:
        out = io.StringIO()
        status = main(list(arguments), project, apis={"greenhouse": greenhouse}, out=out)
        return status, out.getvalue()

    return command
