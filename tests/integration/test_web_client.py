import json
import threading
from collections.abc import Iterator
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from hunter.adapters.web_client import USER_AGENT, WebClient, WebError
from hunter.domain.pacing import Pacing, PaceRule

ROBOTS = "User-agent: *\nDisallow: /private\n"


class Site(BaseHTTPRequestHandler):
    """A small real web server: JSON, text, a rate limit that clears, a missing page, robots."""

    hits: dict[str, int] = {}

    def answer_get(self) -> None:
        self.hits[self.path] = self.hits.get(self.path, 0) + 1
        if self.path == "/robots.txt":
            self.answer(200, ROBOTS)
        elif self.path.startswith("/jobs"):
            self.answer(200, json.dumps({"path": self.path, "agent": self.headers["User-Agent"]}))
        elif self.path == "/busy" and self.hits[self.path] == 1:
            self.answer(429, "slow down", retry_after="0")
        elif self.path in {"/busy", "/public", "/private"}:
            self.answer(200, "<html>a page</html>")
        else:
            self.answer(404, "missing")

    def answer_post(self) -> None:
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.answer(200, json.dumps({"echo": json.loads(body)}))

    def answer(self, status: int, text: str, retry_after: str | None = None) -> None:
        self.send_response(status)
        if retry_after is not None:
            self.send_header("Retry-After", retry_after)
        self.end_headers()
        self.wfile.write(text.encode())

    def log_message(self, *_: object) -> None:
        return


# http.server looks up `do_<METHOD>`, a name the naming rules don't allow to be written out.
for method in ("GET", "POST"):
    setattr(Site, f"do_{method}", getattr(Site, f"answer_{method.lower()}"))


@pytest.fixture
def site() -> Iterator[str]:
    Site.hits = {}
    server = ThreadingHTTPServer(("127.0.0.1", 0), Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def waits() -> list[float]:
    return []


@pytest.fixture
def client(waits: list[float]) -> WebClient:
    pacing = Pacing({}, default=PaceRule(min_gap=timedelta(seconds=5)))
    return WebClient(pacing, sleep=waits.append)


def test_json_with_query_parameters_and_hunters_user_agent(client: WebClient, site: str) -> None:
    answer = client.get_json(f"{site}/jobs", params={"page": "2"})
    assert answer == {"path": "/jobs?page=2", "agent": USER_AGENT}


def test_a_post_with_a_json_body(client: WebClient, site: str) -> None:
    assert client.post_json(f"{site}/search", {"keyword": "python"}) == {
        "echo": {"keyword": "python"}
    }


def test_the_second_request_to_a_host_is_paced(
    client: WebClient, site: str, waits: list[float]
) -> None:
    client.get_json(f"{site}/jobs")
    client.get_json(f"{site}/jobs")
    assert len(waits) == 1
    assert 4 < waits[0] <= 5


def test_a_rate_limit_is_retried_after_the_time_it_asks_for(client: WebClient, site: str) -> None:
    assert client.get_text(f"{site}/busy") == "<html>a page</html>"
    assert Site.hits["/busy"] == 2


def test_a_missing_page_raises_with_its_status(client: WebClient, site: str) -> None:
    with pytest.raises(WebError) as raised:
        client.get_text(f"{site}/gone")
    assert raised.value.status == 404


def test_pages_follow_robots_txt(client: WebClient, site: str) -> None:
    assert client.get_page(f"{site}/public") == "<html>a page</html>"
    with pytest.raises(WebError, match="robots.txt"):
        client.get_page(f"{site}/private")
    assert "/private" not in Site.hits
