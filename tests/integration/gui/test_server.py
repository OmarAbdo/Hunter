import json
import shutil
import threading
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from hunter.adapters.cli.project import Project
from hunter.adapters.gui.server import gui_server

REPOSITORY = Path(__file__).resolve().parents[3]


@pytest.fixture
def address(tmp_path: Path) -> Iterator[str]:
    shutil.copytree(REPOSITORY / "campaigns", tmp_path / "campaigns")
    server = gui_server(Project(tmp_path))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def read(url: str) -> tuple[int, str, str]:
    try:
        with urllib.request.urlopen(url, timeout=10) as answer:
            return answer.status, answer.headers["Content-Type"], answer.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.headers["Content-Type"] or "", ""


def test_the_page_is_served(address: str) -> None:
    status, kind, page = read(f"{address}/")
    assert (status, kind) == (200, "text/html; charset=utf-8")
    assert "<title>Hunter</title>" in page


def test_the_campaigns_come_as_json(address: str) -> None:
    status, kind, body = read(f"{address}/api/campaigns")
    assert (status, kind) == (200, "application/json")
    assert [campaign["id"] for campaign in json.loads(body)] == ["de-swe-berlin"]


def test_a_campaign_s_jobs_and_the_companies_and_the_pool_come_as_json(address: str) -> None:
    assert json.loads(read(f"{address}/api/jobs?campaign=de-swe-berlin")[2]) == []
    assert json.loads(read(f"{address}/api/companies")[2]) == []
    assert json.loads(read(f"{address}/api/pool")[2]) == {"jobs": 0, "companies": 0, "boards": 0}


def test_anything_else_is_not_found(address: str) -> None:
    assert read(f"{address}/api/nothing")[0] == 404
    assert read(f"{address}/../var/accounts.toml")[0] == 404


def test_the_window_saying_it_is_open_is_heard(address: str) -> None:
    assert read(f"{address}/api/alive")[0] == 200
