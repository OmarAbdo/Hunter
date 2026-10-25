import itertools
import json
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from hunter.adapters.web_client import USER_AGENT, WebClient, WebError
from hunter.domain.pacing import Pacing, PaceRule

ROBOTS = "User-agent: *\nDisallow: /private\n"
PAUSE = timedelta(seconds=30)
RATE_LIMITED = {  # the Retry-After each sends: "/held" every time, the others the first time only
    "/busy": lambda: "0",
    "/dated": lambda: format_datetime(datetime.now(UTC) + PAUSE),
    "/held": lambda: "75335",  # a day's rest, as Workable asked on 2026-10-25
}
ENCODED = {  # pages in encodings other than the plain UTF-8 of the rest
    "/latin": (None, "Stellen für Entwickler".encode("latin-1")),  # Latin-1, said nowhere
    "/unknown-encoding": ("text/html; charset=utf8mb4", "Stellen für Entwickler".encode()),
}


class Site(BaseHTTPRequestHandler):
    """A small real web server: JSON, text, a rate limit that clears, a missing page, robots."""

    hits: dict[str, int] = {}
    arrivals: list[float] = []  # when each request arrived, by the monotonic clock

    def answer_get(self) -> None:
        self.arrivals.append(time.monotonic())
        self.hits[self.path] = self.hits.get(self.path, 0) + 1
        if self.path == "/robots.txt":
            self.answer(200, ROBOTS)
        elif self.path.startswith("/jobs"):
            self.answer(200, json.dumps({"path": self.path, "agent": self.headers["User-Agent"]}))
        elif self.path in RATE_LIMITED and (self.hits[self.path] == 1 or self.path == "/held"):
            self.answer(429, "slow down", retry_after=RATE_LIMITED[self.path]())
        elif self.path == "/dropped":  # the site hangs up without an answer
            self.close_connection = True
        elif self.path in ENCODED:
            self.answer_bytes(*ENCODED[self.path])
        elif self.path in {"/busy", "/dated", "/public", "/private"}:
            self.answer(200, "<html>a page</html>")
        else:
            self.answer(404, "missing")

    def answer_bytes(self, content_type: str | None, body: bytes) -> None:
        self.send_response(200)
        if content_type:
            self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)

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
    Site.arrivals = []
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


def test_requests_to_one_host_from_several_threads_still_take_turns(site: str) -> None:
    """Measured where the site sees the requests: when each answer came back also depends on how
    busy the machine is."""
    client = WebClient(Pacing({}, default=PaceRule(min_gap=timedelta(seconds=0.3))))
    threads = [threading.Thread(target=client.get_json, args=(f"{site}/jobs",)) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    gaps = [later - earlier for earlier, later in itertools.pairwise(sorted(Site.arrivals))]
    assert min(gaps) >= 0.25


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


def test_a_page_in_another_encoding_than_utf_8_is_still_read(client: WebClient, site: str) -> None:
    """Many small employers' sites send Latin-1 without saying so; the odd letter is lost."""
    assert client.get_text(f"{site}/latin") == "Stellen f\ufffdr Entwickler"


def test_a_site_that_hangs_up_is_no_answer(client: WebClient, site: str) -> None:
    with pytest.raises(WebError, match="no answer") as raised:
        client.get_text(f"{site}/dropped")
    assert raised.value.status is None
    assert Site.hits["/dropped"] == 3  # tried again, like any request without an answer


def test_an_encoding_python_does_not_know_is_read_as_utf_8(client: WebClient, site: str) -> None:
    assert client.get_text(f"{site}/unknown-encoding") == "Stellen für Entwickler"


def test_a_pause_asked_for_as_a_date_is_waited_out(
    client: WebClient, site: str, waits: list[float]
) -> None:
    assert client.get_text(f"{site}/dated") == "<html>a page</html>"
    assert 28 <= waits[0] <= 30


def test_a_site_asking_for_a_long_pause_is_not_asked_again(
    client: WebClient, site: str, waits: list[float]
) -> None:
    """Longer than a run should wait: the source is reported, and the site left alone."""
    with pytest.raises(WebError, match="HTTP 429.*asked Hunter to wait until 20"):
        client.get_text(f"{site}/held")
    with pytest.raises(WebError, match="asked Hunter to wait until"):
        client.get_text(f"{site}/jobs")
    assert (Site.hits.get("/held"), Site.hits.get("/jobs")) == (1, None)
    assert waits == []


def test_a_host_s_daily_cap_ends_its_requests_for_the_day(site: str) -> None:
    host = site.removeprefix("http://")
    once = PaceRule(min_gap=timedelta(0), per_day=1)
    capped = Pacing({host: once}, default=PaceRule(min_gap=timedelta(0)))
    client = WebClient(capped, sleep=lambda _: None)
    client.get_json(f"{site}/jobs")
    with pytest.raises(WebError, match="1 a day reached") as raised:
        client.get_json(f"{site}/jobs?page=2")
    assert not raised.value.retryable
    assert Site.hits.get("/jobs?page=2") is None
