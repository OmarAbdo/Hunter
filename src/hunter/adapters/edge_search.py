"""Web search through Microsoft Edge, for finding a company's board and an employer's own ad: Hunter
searches like a person, in a real browser and politely paced, not through a paid API. Edge runs
headless with a profile of its own and hands back the page it rendered; only the result links are
read, through the engines' redirects. The engines take turns (domain/search_turns.py): each search
goes to the one used longest ago, an engine at its share of the last hour waits, and one that
showed a challenge (a captcha) rests; an engine answering with a challenge or not at all is passed
over for the next. Every search is logged with its outcome, and the turns are read from the log,
so they hold across runs. Edge names itself as an ordinary Edge: DuckDuckGo met headless Edge's own
name with a captcha at once (2026-10-27)."""

import base64
import re
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote, urlsplit

from hunter.adapters.storage.search_log import Outcome, Searched, SearchLog
from hunter.application.ports import SourceUnavailableError
from hunter.domain.search_turns import Turns, next_engines

EDGE = (
    Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
)
TIMEOUT = 60  # seconds for one page; Edge took 3 to 15
VERSION = re.compile(r"(\d+)\.\d+\.\d+\.\d+")  # the folders beside msedge.exe
YAHOO_REDIRECT = re.compile(r"/RU=([^/]+)/R[KS]=")
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


def yahoo_target(link: str) -> str | None:
    """Where a result leads: Yahoo's redirect carries it in its path, between `/RU=` and `/RK=`."""
    if not urlsplit(link).netloc.endswith("r.search.yahoo.com"):
        return link
    found = YAHOO_REDIRECT.search(link)
    return unquote(found[1]) if found else None


def same(link: str) -> str | None:
    """The engines whose result links lead to the result itself."""
    return link


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
        if links := list(dict.fromkeys(link for link in found if link)):
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
# The engines found to answer headless Edge with results (2026-11-08). Mojeek asks for a
# challenge at once, Qwant's full site answers 403 and Google a captcha, so they're left out. None
# of these is known by its challenge page yet: an answer without results is "failed", and the
# engine rests (domain/search_turns.py).
STARTPAGE = Engine(
    "startpage",
    "https://www.startpage.com/do/search?q={}",
    re.compile(r'<a\b[^>]*\bhref="([^"]+)"[^>]*\bclass="wgl-site-title'),
    'class="w-gl',
    (),
    same,
)
BRAVE = Engine(
    "brave",
    "https://search.brave.com/search?q={}",
    re.compile(r'data-type="web"[^>]*>.*?<a\b[^>]*\bhref="([^"]+)"', re.S),
    'id="mixed-main"',
    (),
    same,
)
ECOSIA = Engine(
    "ecosia",
    "https://www.ecosia.org/search?q={}",
    re.compile(r'<a\b[^>]*\bdata-test-id="result-link"[^>]*\bhref="([^"]+)"'),
    'data-test-id="mainline"',
    (),
    same,
)
YAHOO = Engine(
    "yahoo",
    "https://search.yahoo.com/search?p={}",
    re.compile(r'<div class="compTitle[^"]*">\s*<a\b[^>]*\bhref="([^"]+)"'),
    'id="web"',
    (),
    yahoo_target,
)
SWISSCOWS = Engine(
    "swisscows",
    "https://swisscows.com/en/web?query={}",
    re.compile(
        r'<article\b[^>]*class="item web-page"[^>]*>\s*<header>\s*'
        r'<a\b[^>]*\bhref="([^"]+)"'
    ),
    'class="web-results',
    (),
    same,
)
# Qwant's lite site and Seznam mark only their results, so an empty answer reads as unreadable.
QWANT = Engine(
    "qwant",
    "https://lite.qwant.com/?q={}",
    re.compile(r'data-testid="webResult"[^>]*>.*?<a\b[^>]*\bhref="([^"]+)"', re.S),
    'data-testid="webResult"',
    (),
    same,
)
SEZNAM = Engine(
    "seznam",
    "https://search.seznam.cz/?q={}",
    re.compile(r'data-e-a="heading"\s+href="([^"]+)"'),
    'data-e-a="heading"',
    (),
    same,
)


def searxng(server: str) -> Engine:
    """A public SearXNG server: a metasearch engine many people run, each with its own address
    and its own limits, all with the same results page."""
    return Engine(
        server.partition("/")[0],
        f"https://{server}/search?q={{}}",
        re.compile(r'<article class="result[^"]*"[^>]*>.*?<a\b[^>]*\bhref="([^"]+)"', re.S),
        'id="urls"',
        (),
        same,
    )


# The public servers that answered headless Edge with results that fit the query (2026-11-08), of
# 20 tried. search.inetol.net, search.rhscz.eu and searx.oloke.xyz answered short queries well but
# longer quoted ones, an employer's ad's, with pages unrelated to them, so they're left out.
SEARXNG = tuple(
    searxng(server) for server in ("priv.au", "etsi.me", "darmarit.org/searx", "paulgo.io")
)
ENGINES = (DUCKDUCKGO, BING, STARTPAGE, BRAVE, ECOSIA, YAHOO, SWISSCOWS, QWANT, SEZNAM, *SEARXNG)


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Pace:
    gap: timedelta = timedelta(seconds=5)  # between any two searches, on any engine
    turns: Turns = Turns()
    now: Callable[[], datetime] = utc_now
    sleep: Callable[[float], None] = time.sleep


class EdgeSearch:
    """Hunter's web search (application/ports.py). Its pace is read from the log, so it holds
    across runs and processes sharing the database."""

    def __init__(
        self,
        browse: Callable[[str], str],
        log: SearchLog,
        pace: Pace | None = None,
        engines: Sequence[Engine] = ENGINES,
    ):
        """`browse` gives a page as a browser shows it: `Edge(profile).dom`."""
        self.browse, self.log, self.pace = browse, log, pace or Pace()
        self.engines = {engine.name: engine for engine in engines}

    def links(self, query: str) -> list[str]:
        """The first answer's result links, best first. Raises SourceUnavailableError."""
        now = self.pace.now()
        uses = self.log.uses(list(self.engines), now - self.pace.turns.longest_rest)
        turn = next_engines(uses, now, self.pace.turns)
        if not turn:
            raise SourceUnavailableError("web search: every engine is resting or at its share")
        failures = []
        for name in turn:
            outcome, links = self.search(self.engines[name], query)
            if outcome in ("links", "nothing"):
                return links
            failures.append(f"{name}: {outcome}")
        raise SourceUnavailableError("web search: " + ", ".join(failures))

    def search(self, engine: Engine, query: str) -> tuple[str, list[str]]:
        last = self.log.last()
        if last and (wait := self.pace.gap - (self.pace.now() - last)) > timedelta(0):
            self.pace.sleep(wait.total_seconds())
        try:
            outcome, links = engine.read(self.browse(engine.url(query)))
        except SourceUnavailableError:
            outcome, links = "failed", []
        self.log.record(Searched(engine.name, query, outcome, len(links), self.pace.now()))
        return outcome, links
