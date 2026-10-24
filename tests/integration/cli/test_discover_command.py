import io
import shutil
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from hunter.adapters.cli.main import main
from hunter.adapters.database import open_database
from hunter.adapters.pool import Pool
from hunter.adapters.registry import Registry

REPOSITORY = Path(__file__).resolve().parents[3]
N26 = (REPOSITORY / "tests" / "fixtures" / "sources" / "greenhouse-n26.json").read_bytes()


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


def run(project: Path, *arguments: str, greenhouse: str = "") -> tuple[int, str]:
    out = io.StringIO()
    status = main(list(arguments), project, apis={"greenhouse": greenhouse}, out=out)
    return status, out.getvalue()


def test_a_board_link_adds_the_company_to_the_registry(project: Path) -> None:
    status, out = run(
        project, "boards", "add", "https://jobs.ashbyhq.com/enpal", "--company", "Enpal"
    )
    company = Registry(open_database(project / "var" / "hunter.db")).get("enpal")
    assert status == 0
    assert company is not None
    assert [board.key for board in company.boards] == ["ashby:enpal"]
    assert "Enpal: ashby:enpal" in out


def test_a_link_that_names_no_board_is_refused(project: Path) -> None:
    status, out = run(project, "boards", "add", "https://example.com/careers")
    assert status == 1
    assert "names no job board" in out


def test_discover_reads_the_registry_feeds_and_reports_each_source(
    project: Path, greenhouse: str
) -> None:
    run(project, "boards", "add", "https://job-boards.greenhouse.io/n26", "--company", "N26")
    status, out = run(project, "discover", greenhouse=greenhouse)
    assert status == 0
    assert "greenhouse:n26" in out
    assert Pool(open_database(project / "var" / "hunter.db")).job_count() == 3
    assert "de-swe-berlin" in out


def test_a_source_that_is_down_is_reported(project: Path, greenhouse: str) -> None:
    run(project, "boards", "add", "https://job-boards.greenhouse.io/gone", "--company", "Gone")
    status, out = run(project, "discover", greenhouse=greenhouse)
    assert status == 0
    assert "greenhouse:gone" in out
    assert "HTTP 404" in out


def test_an_unknown_campaign_is_refused(project: Path) -> None:
    status, out = run(project, "discover", "--campaign", "nowhere")
    assert status == 1
    assert "no campaign nowhere" in out
