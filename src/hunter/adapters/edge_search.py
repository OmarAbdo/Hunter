"""Web search through Microsoft Edge, probing's last way to find a company's board: Hunter searches
like a person, in a real browser and politely paced, not through a paid API. Edge runs headless
with a profile of its own and hands back the page it rendered; only the result links are read,
through the engines' redirects. DuckDuckGo's plain-HTML results come first, then Bing's; an engine
answering with a challenge (a captcha) or not at all is passed over for the next. Every search is
logged with its outcome. Edge names itself as an ordinary Edge: DuckDuckGo met headless Edge's own
name with a captcha at once (2026-10-27)."""

import base64
import re
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlsplit

from hunter.adapters.storage.search_log import Outcome, Searched, SearchLog
from hunter.application.ports import SourceUnavailableError

EDGE = (
    Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
)
TIMEOUT = 60  # seconds for one page; Edge took 3 to 15
VERSION = re.compile(r"(\d+)\.\d+\.\d+\.\d+")  # the folders beside msedge.exe
AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/{0}.0.0.0 Safari/537.36 Edg/{0}.0.0.0"
)
Run = Callable[..., subprocess.CompletedProcess[bytes]]


class Edge:
    def __init__(self, profile: Path, paths: Sequence[Path] = EDGE, run: Run = subprocess.run):
        """`profile` is the user-data folder for Hunter's searches, apart from Omar's own."""
        self.profile, self.paths, self.run = profile, paths, run

    def dom(self, url: str) -> str:
        """The page as Edge shows it once its scripts ran. Raises SourceUnavailableError."""
        edge = next((path for path in self.paths if path.is_file()), None)
        if edge is None:
            raise SourceUnavailableError("edge: not installed")
        command = [str(edge), "--headless=new", "--disable-gpu", f"--user-data-dir={self.profile}"]
        command += ["--virtual-time-budget=5000", f"--user-agent={agent(edge)}", "--dump-dom", url]
        try:
            done = self.run(command, capture_output=True, timeout=TIMEOUT)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SourceUnavailableError(f"edge: {error}") from error
        page = done.stdout.decode("utf-8", errors="replace")
        if done.returncode or not page.strip():
            raise SourceUnavailableError(f"edge: no page (exit code {done.returncode})")
        return page


def agent(edge: Path) -> str:
    """The user agent of the Edge installed, as its ordinary windows send it."""
    folders = (VERSION.fullmatch(folder.name) for folder in edge.parent.iterdir())
    return AGENT.format(max((int(found[1]) for found in folders if found), default=156))


def duckduckgo_target(link: str) -> str | None:
    """Where a result leads: DuckDuckGo's redirect carries it in `uddg`; ads lead to `/y.js`."""
    parts = urlsplit(link)
    if parts.netloc.endswith("duckduckgo.com"):
        return parse_qs(parts.query).get("uddg", [None])[0]
    return link


def bing_target(link: str) -> str | None:
    """Where a result leads: Bing's redirect carries it in `u`, in base64 behind `a1`."""
    parts = urlsplit(link)
    coded = parse_qs(parts.query).get("u", [""])[0].removeprefix("a1")
    if coded:
        return base64.urlsafe_b64decode(coded + "=" * (-len(coded) % 4)).decode(errors="replace")
    return None if parts.netloc.endswith("bing.com") else link


@dataclass(frozen=True)
class Engine:
    name: str
    address: str  # the search's URL, {} for the query
    result: re.Pattern[str]  # a result's link
    results: str  # on every results page, empty or not
    challenges: tuple[str, ...]  # on a challenge page only
    target: Callable[[str], str | None]

    def url(self, query: str) -> str:
        return self.address.format(quote_plus(query))

    def read(self, page: str) -> tuple[Outcome, list[str]]:
        """The search's outcome and its result links, best first."""
        if any(challenge in page for challenge in self.challenges):
            return "captcha", []
        found = (self.target(link.replace("&amp;", "&")) for link in self.result.findall(page))
        if links := [link for link in found if link]:
            return "links", links
        return ("nothing" if self.results in page else "failed"), []


DUCKDUCKGO = Engine(
    "duckduckgo",
    "https://html.duckduckgo.com/html/?q={}",
    re.compile(r'<a\b[^>]*\bclass="result__a"[^>]*\bhref="([^"]+)"'),
    'id="links"',
    ("anomaly-modal", 'id="challenge-form"'),
    duckduckgo_target,
)
BING = Engine(
    "bing",
    "https://www.bing.com/search?q={}",
    re.compile(r'<li class="b_algo"[^>]*>.*?<h2[^>]*>\s*<a\b[^>]*\bhref="([^"]+)"', re.S),
    'id="b_results"',
    ("/turing/captcha", "turingChallenge"),
    bing_target,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Pace:
    gap: timedelta = timedelta(seconds=5)  # between any two searches, on any engine
    per_day: int = 50  # per engine and UTC day, about what a busy person searches
    now: Callable[[], datetime] = utc_now
    sleep: Callable[[float], None] = time.sleep


class EdgeSearch:
    """Hunter's web search (application/ports.py). Its pace is read from the log, so it holds
    across runs and processes sharing the database."""

    def __init__(self, browse: Callable[[str], str], log: SearchLog, pace: Pace | None = None):
        """`browse` gives a page as a browser shows it: `Edge(profile).dom`."""
        self.browse, self.log, self.pace = browse, log, pace or Pace()

    def links(self, query: str) -> list[str]:
        """The first answer's result links, best first. Raises SourceUnavailableError."""
        failures = []
        for engine in (DUCKDUCKGO, BING):
            outcome, links = self.search(engine, query)
            if outcome in ("links", "nothing"):
                return links
            failures.append(f"{engine.name}: {outcome}")
        raise SourceUnavailableError("web search: " + ", ".join(failures))

    def search(self, engine: Engine, query: str) -> tuple[str, list[str]]:
        today = self.pace.now().astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        if self.log.count(engine.name, today) >= self.pace.per_day:
            return "daily cap reached", []
        last = self.log.last()
        if last and (wait := self.pace.gap - (self.pace.now() - last)) > timedelta(0):
            self.pace.sleep(wait.total_seconds())
        try:
            outcome, links = engine.read(self.browse(engine.url(query)))
        except SourceUnavailableError:
            outcome, links = "failed", []
        self.log.record(Searched(engine.name, query, outcome, len(links), self.pace.now()))
        return outcome, links
