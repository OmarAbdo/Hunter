import json
import threading
import time
import urllib.request
from collections.abc import Iterator

import pytest

from hunter.adapters.cli.project import Project
from hunter.adapters.gui.server import gui_server


@pytest.fixture
def address(quiet_project: Project) -> Iterator[str]:
    """The window's server for a project whose sources answer locally, with nothing."""
    server = gui_server(quiet_project)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    yield url
    for _ in range(200):  # a run a test started ends before its project goes
        if not json.loads(read(f"{url}/api/runs/live")[2])["running"]:
            break
        time.sleep(0.05)
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


def test_hunter_s_icon_is_served_for_the_window(address: str) -> None:
    status, kind, icon = read(f"{address}/hunter.svg")
    assert (status, kind) == (200, "image/svg+xml")
    assert icon.startswith("<svg")


def test_the_campaigns_come_as_json(address: str) -> None:
    status, kind, body = read(f"{address}/api/campaigns")
    assert (status, kind) == (200, "application/json")
    assert [campaign["id"] for campaign in json.loads(body)] == ["de-swe-berlin"]


def test_a_campaign_s_jobs_and_the_companies_and_the_pool_come_as_json(address: str) -> None:
    assert json.loads(read(f"{address}/api/jobs?campaign=de-swe-berlin")[2]) == []
    assert json.loads(read(f"{address}/api/companies")[2]) == []
    assert json.loads(read(f"{address}/api/pool")[2]) == {"jobs": 0, "companies": 0, "boards": 0}
    assert json.loads(read(f"{address}/api/held")[2]) == []


def test_anything_else_is_not_found(address: str) -> None:
    assert read(f"{address}/api/nothing")[0] == 404
    assert read(f"{address}/../var/accounts.toml")[0] == 404


def test_the_window_saying_it_is_open_is_heard(address: str) -> None:
    assert read(f"{address}/api/alive")[0] == 200


def post(url: str) -> int:
    request = urllib.request.Request(url, data=b"", method="POST")
    with urllib.request.urlopen(request, timeout=10) as answer:
        return int(answer.status)


def test_without_a_run_there_is_nothing_to_pause_or_stop(address: str) -> None:
    for action in ("pause", "resume", "stop"):
        with pytest.raises(urllib.error.HTTPError) as refused:
            post(f"{address}/api/runs/{action}")
        assert refused.value.code == 409


def test_a_run_can_be_started_and_followed(address: str) -> None:
    assert post(f"{address}/api/runs") == 202
    live = json.loads(read(f"{address}/api/runs/live")[2])
    assert set(live) == {"running", "paused", "stopping", "lines"}
    assert isinstance(json.loads(read(f"{address}/api/runs")[2]), list)
