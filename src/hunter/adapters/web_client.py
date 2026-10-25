"""Hunter's one way to talk to websites (docs/sources.md):
- every request waits its turn under its host's pace, and gives up after 30 seconds;
- a rate limit, a server error or no answer is tried again, three tries in all, after the pause
  the site asks for. A site that asks for longer than a run should wait isn't asked again until
  then;
- web pages are read only where the site's robots.txt allows it."""

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.robotparser import RobotFileParser

from hunter.adapters.web_answers import NO_ANSWER, decoded, retry_after
from hunter.domain.pacing import CapReachedError, Moment, Pacing

USER_AGENT = "Hunter/0.1 (personal job search)"
TIMEOUT_SECONDS = 30
TRIES = 3
PAUSES_SECONDS = (5.0, 15.0)
LONGEST_PAUSE_SECONDS = 600.0  # the longest pause Hunter waits out within a run
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
FORBIDDEN_STATUSES = frozenset({401, 403})


class WebError(Exception):
    """A failed request. `status` is the HTTP status, or None when no answer came; a `final` one
    isn't worth trying again, whatever its status."""

    def __init__(
        self,
        message: str,
        status: int | None = None,
        retry_after: float | None = None,
        *,
        final: bool = False,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after
        self.final = final

    @property
    def retryable(self) -> bool:
        return not self.final and (self.status is None or self.status in RETRY_STATUSES)


def when(moment: datetime) -> str:
    return f"{moment:%Y-%m-%d %H:%M} UTC"


def moment_now() -> Moment:
    return Moment(wall=datetime.now(UTC), steady=time.monotonic())


class WebClient:
    def __init__(
        self,
        pacing: Pacing,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], Moment] = moment_now,
    ) -> None:
        self.pacing = pacing
        self.sleep = sleep
        self.clock = clock
        self.robots: dict[str, RobotFileParser] = {}
        self.turns: dict[str, threading.Lock] = {}
        self.turns_lock = threading.Lock()

    def get_json(
        self,
        url: str,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        return json.loads(self.get_text(url, params, headers))

    def post_json(self, url: str, body: object, headers: Mapping[str, str] | None = None) -> Any:
        sent = {"Content-Type": "application/json", **(headers or {})}
        return json.loads(self._send(url, sent, json.dumps(body).encode()))

    def get_text(
        self,
        url: str,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> str:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        return self._send(url, headers or {})

    def get_page(self, url: str) -> str:
        """A public web page, read only where the site's robots.txt allows it."""
        if not self._robots_of(url).can_fetch(USER_AGENT, url):
            raise WebError(f"robots.txt disallows {url}")
        return self.get_text(url)

    def _robots_of(self, url: str) -> RobotFileParser:
        parts = urllib.parse.urlsplit(url)
        site = f"{parts.scheme}://{parts.netloc}"
        if site not in self.robots:
            self.robots[site] = self._read_robots(site)
        return self.robots[site]

    def _read_robots(self, site: str) -> RobotFileParser:
        """Read the standard way: a missing file allows everything, a forbidden one nothing."""
        rules = RobotFileParser()
        try:
            rules.parse(self.get_text(f"{site}/robots.txt").splitlines())
        except WebError as error:
            if error.retryable:
                raise
            forbidden = error.status in FORBIDDEN_STATUSES
            rules.parse(["User-agent: *", "Disallow: /"] if forbidden else [])
        return rules

    def _send(self, url: str, headers: Mapping[str, str], body: bytes | None = None) -> str:
        request = urllib.request.Request(url, body, {"User-Agent": USER_AGENT, **headers})
        for attempt in range(1, TRIES):
            try:
                return self._read(request)
            except WebError as error:
                self._pause_before_retry(error, attempt, request.host)
        return self._read(request)

    def _pause_before_retry(self, error: WebError, attempt: int, host: str) -> None:
        if not error.retryable:
            raise error
        pause = error.retry_after if error.retry_after is not None else PAUSES_SECONDS[attempt - 1]
        if pause > LONGEST_PAUSE_SECONDS:
            until = self.clock().wall + timedelta(seconds=pause)
            self.pacing.hold(host, until)
            message = f"{error}; asked Hunter to wait until {when(until)}"
            raise WebError(message, error.status, pause) from error
        self.sleep(pause)

    def _read(self, request: urllib.request.Request) -> str:
        self._wait_turn(request.host)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return decoded(response.read(), response.headers.get_content_charset())
        except urllib.error.HTTPError as error:
            message = f"{request.host}: HTTP {error.code} for {request.full_url}"
            pause = retry_after(error, self.clock().wall)
            error.close()  # an error answer is a response too; left open, it's closed at exit
            raise WebError(message, error.code, pause) from error
        except NO_ANSWER as error:
            raise WebError(f"{request.host}: no answer ({error})") from error

    def _wait_turn(self, host: str) -> None:
        """One request at a time per host, also when several threads read the same site."""
        with self._turn_of(host):
            now = self.clock()
            try:
                pause = self.pacing.wait(host, now)
            except CapReachedError as error:  # Hunter's own budget for the site, used up today
                raise WebError(str(error), final=True) from error
            if pause.total_seconds() > LONGEST_PAUSE_SECONDS:
                message = f"{host}: asked Hunter to wait until {when(now.wall + pause)}"
                raise WebError(message, None, pause.total_seconds())
            if pause:
                self.sleep(pause.total_seconds())
            self.pacing.record(host, self.clock())

    def _turn_of(self, host: str) -> threading.Lock:
        with self.turns_lock:
            return self.turns.setdefault(host, threading.Lock())
