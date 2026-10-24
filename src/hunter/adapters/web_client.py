"""The one way Hunter talks to websites: a timeout on every call, per-host pacing, retries on rate
limits and server errors, and robots.txt for pages (docs/sources.md)."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from hunter.domain.pacing import Pacing

USER_AGENT = "Hunter/0.1 (personal job search)"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
TRIES = 3
TIMEOUT_SECONDS = 30
LONGEST_RETRY_AFTER_SECONDS = 600.0
FORBIDDEN = frozenset({401, 403})
SERVER_ERRORS = 500


class WebError(Exception):
    def __init__(self, message: str, status: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.status, self.retry_after = status, retry_after


def utc_now() -> datetime:
    return datetime.now(UTC)


def retry_after_seconds(value: str | None) -> float | None:
    """The seconds a Retry-After header asks for; None when it gives a date or nothing."""
    if value is None or not value.strip().isdigit():
        return None
    return min(float(value), LONGEST_RETRY_AFTER_SECONDS)


class WebClient:
    def __init__(
        self,
        pacing: Pacing,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.pacing, self.sleep, self.clock = pacing, sleep, clock
        self.robots: dict[str, urllib.robotparser.RobotFileParser] = {}

    def get_json(
        self, url: str, params: Mapping[str, str] | None = None, headers: Mapping[str, str] = {}
    ) -> Any:
        return json.loads(self.get_text(url, params, headers))

    def post_json(self, url: str, body: object, headers: Mapping[str, str] = {}) -> Any:
        sent = {"Content-Type": "application/json", "User-Agent": USER_AGENT, **headers}
        data = json.dumps(body).encode()
        return json.loads(self._fetch(urllib.request.Request(url, data, sent, method="POST")))

    def get_text(
        self, url: str, params: Mapping[str, str] | None = None, headers: Mapping[str, str] = {}
    ) -> str:
        full_url = f"{url}?{urllib.parse.urlencode(params)}" if params else url
        return self._fetch(
            urllib.request.Request(full_url, None, {"User-Agent": USER_AGENT, **headers})
        )

    def get_page(self, url: str) -> str:
        """A public web page, only where the site's robots.txt allows it."""
        if not self._allowed(url):
            raise WebError(f"robots.txt disallows {url}")
        return self.get_text(url)

    def _allowed(self, url: str) -> bool:
        parts = urllib.parse.urlsplit(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root not in self.robots:
            self.robots[root] = self._read_robots(root)
        return self.robots[root].can_fetch(USER_AGENT, url)

    def _read_robots(self, root: str) -> urllib.robotparser.RobotFileParser:
        """As robots.txt is meant to be read: missing allows all, forbidden allows nothing."""
        parser = urllib.robotparser.RobotFileParser()
        try:
            parser.parse(self.get_text(f"{root}/robots.txt").splitlines())
        except WebError as error:
            if error.status is None or error.status >= SERVER_ERRORS:
                raise
            parser.parse(["User-agent: *", "Disallow: /"] if error.status in FORBIDDEN else [])
        return parser

    def _fetch(self, request: urllib.request.Request) -> str:
        host = urllib.parse.urlsplit(request.full_url).hostname or request.full_url
        for attempt in range(1, TRIES):
            answer = self._try_once(request, host, attempt)
            if isinstance(answer, str):
                return answer
            self.sleep(answer)
        return self._once(request, host)

    def _try_once(self, request: urllib.request.Request, host: str, attempt: int) -> str | float:
        """The answer, or the seconds to wait before trying again."""
        try:
            return self._once(request, host)
        except WebError as error:
            if error.status is not None and error.status not in RETRY_STATUSES:
                raise
            return error.retry_after if error.retry_after is not None else 5.0 * 3 ** (attempt - 1)

    def _once(self, request: urllib.request.Request, host: str) -> str:
        self._pace(host)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return str(response.read().decode(charset))
        except urllib.error.HTTPError as error:
            wait = retry_after_seconds(error.headers.get("Retry-After"))
            message = f"{host}: HTTP {error.code} for {request.full_url}"
            raise WebError(message, error.code, wait) from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise WebError(f"{host}: {error}") from error

    def _pace(self, host: str) -> None:
        wait = self.pacing.wait(host, self.clock())
        if wait > timedelta(0):
            self.sleep(wait.total_seconds())
        self.pacing.record(host, self.clock())
