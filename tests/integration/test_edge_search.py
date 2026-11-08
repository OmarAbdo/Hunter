import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from hunter.adapters.edge_search import BING, DUCKDUCKGO, Edge, EdgeSearch, Pace
from hunter.adapters.storage.database import open_database
from hunter.adapters.storage.search_log import Searched, SearchLog
from hunter.application.ports import SourceUnavailableError

SAVED = Path(__file__).resolve().parents[1] / "fixtures" / "sources"
NOON = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
ZALANDO_BOARD = "https://zalando.wd3.myworkdayjobs.com/ZalandoSiteWD/"


def saved(name: str) -> str:
    return (SAVED / f"edge-search-{name}.html").read_text(encoding="utf-8")


def test_result_links_are_read_through_each_engines_redirects() -> None:
    zalando = "https://jobs.zalando.com/"
    ddg = [zalando, ZALANDO_BOARD, "https://builtin.com/company/zalando/jobs"]
    assert DUCKDUCKGO.read(saved("duckduckgo-zalando")) == ("links", ddg)
    bing = [f"{zalando}en/jobs", "https://www.linkedin.com/company/zalando/jobs", ZALANDO_BOARD]
    assert BING.read(saved("bing-zalando")) == ("links", bing)  # the ad isn't a result


def test_a_page_without_results_says_whether_it_is_empty_a_challenge_or_unknown() -> None:
    assert DUCKDUCKGO.read(saved("duckduckgo-nothing")) == ("nothing", [])
    assert DUCKDUCKGO.read(saved("duckduckgo-captcha")) == ("captcha", [])
    assert BING.read('<ol id="b_results"><li class="b_no">No results</li></ol>')[0] == "nothing"
    assert BING.read('<iframe src="/turing/captcha/challenge"></iframe>')[0] == "captcha"
    assert BING.read("<html><body>Something else</body></html>") == ("failed", [])
    assert DUCKDUCKGO.url('"N26" careers jobs').endswith("/html/?q=%22N26%22+careers+jobs")


class Clock:
    def __init__(self) -> None:
        self.time = NOON
        self.slept: list[float] = []

    def now(self) -> datetime:
        return self.time

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.time += timedelta(seconds=seconds)


def searching(tmp_path: Path, **pages: str | None) -> tuple[EdgeSearch, SearchLog, Clock]:
    """A search whose engines show the saved pages, by host; None is a browser that failed."""

    def browse(url: str) -> str:
        page = pages[str(urlsplit(url).hostname).split(".")[-2]]
        if page is None:
            raise SourceUnavailableError("edge: timed out")
        return saved(page)

    log, clock = SearchLog(open_database(tmp_path / "hunter.db")), Clock()
    return EdgeSearch(browse, log, Pace(now=clock.now, sleep=clock.sleep)), log, clock


def test_a_challenge_moves_the_search_on_to_the_next_engine(tmp_path: Path) -> None:
    search, log, clock = searching(tmp_path, duckduckgo="duckduckgo-captcha", bing="bing-zalando")
    assert search.links('"Zalando" careers jobs')[-1] == ZALANDO_BOARD
    assert log.summary(NOON) == {"duckduckgo": {"captcha": 1}, "bing": {"links": 1}}
    assert clock.slept == [5.0]  # one search every 5 seconds, whichever engine
    found = log.database.execute("SELECT engine, query, links, at FROM searches").fetchall()
    assert found[-1] == ("bing", '"Zalando" careers jobs', 3, "2026-10-27T12:00:05+00:00")


def test_an_engine_finding_nothing_is_an_answer(tmp_path: Path) -> None:
    search, log, clock = searching(tmp_path, duckduckgo="duckduckgo-nothing")
    assert search.links('"Nothing" careers jobs') == []
    assert log.summary(NOON) == {"duckduckgo": {"nothing": 1}}
    assert clock.slept == []


def test_when_every_engine_fails_the_search_is_unavailable(tmp_path: Path) -> None:
    search, log, _ = searching(tmp_path, duckduckgo="duckduckgo-captcha", bing=None)
    with pytest.raises(SourceUnavailableError, match="duckduckgo: captcha, bing: failed"):
        search.links('"N26" careers jobs')
    assert log.summary(NOON) == {"duckduckgo": {"captcha": 1}, "bing": {"failed": 1}}


def test_the_engine_used_longest_ago_searches_first_across_runs(tmp_path: Path) -> None:
    search, log, clock = searching(tmp_path, bing="bing-zalando")
    log.record(Searched("duckduckgo", "q", "links", 1, NOON - timedelta(minutes=1)))
    log.record(Searched("bing", "q", "links", 1, NOON - timedelta(minutes=40)))
    assert search.links("q")[-1] == ZALANDO_BOARD
    assert log.summary(NOON)["bing"] == {"links": 1}
    assert clock.slept == []  # the last search was a minute ago, beyond the 5 seconds


def test_with_every_engine_resting_the_search_is_unavailable(tmp_path: Path) -> None:
    search, log, _ = searching(tmp_path)
    for engine in ("duckduckgo", "bing"):
        log.record(Searched(engine, "q", "captcha", 0, NOON - timedelta(minutes=10)))
    with pytest.raises(SourceUnavailableError, match="every engine is resting"):
        search.links("q")


class EdgeRun:
    """Edge's command line without Edge: it answers as told and remembers how it was run."""

    def __init__(
        self, out: bytes = b"<html></html>", code: int = 0, error: Exception | None = None
    ):
        self.answer = out, code, error
        self.commands: list[list[str]] = []
        self.options: dict[str, object] = {}

    def __call__(self, command: list[str], **options: object) -> subprocess.CompletedProcess[bytes]:
        out, code, error = self.answer
        self.commands.append(command)
        self.options = options
        if error:
            raise error
        return subprocess.CompletedProcess(command, code, out, b"")


def installed(tmp_path: Path, *versions: str) -> Path:
    for version in ("", *versions):
        (tmp_path / "Application" / version).mkdir(parents=True, exist_ok=True)
    edge = tmp_path / "Application" / "msedge.exe"
    edge.write_bytes(b"")
    return edge


def test_edge_shows_a_page_headless_as_an_ordinary_edge_would(tmp_path: Path) -> None:
    run = EdgeRun("<html>für</html>".encode())
    edge = Edge(tmp_path / "profile", [installed(tmp_path, "99.0.1.2", "156.0.4314.42")], run)
    assert edge.dom("https://www.bing.com/search?q=N26") == "<html>für</html>"
    command = run.commands[0]
    assert command[0].endswith("msedge.exe")
    assert command[-2:] == ["--dump-dom", "https://www.bing.com/search?q=N26"]
    assert {"--headless=new", f"--user-data-dir={tmp_path / 'profile'}"} <= set(command)
    agent = next(part for part in command if part.startswith("--user-agent="))
    assert agent.endswith(" Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0")  # not HeadlessEdg
    assert run.options["timeout"] == 60
    plain = EdgeRun()
    Edge(tmp_path / "profile", [installed(tmp_path / "bare")], plain).dom("https://example.com")
    assert "Edg/" in " ".join(plain.commands[0])


def test_an_edge_that_fails_times_out_or_is_missing_is_unavailable(tmp_path: Path) -> None:
    edge = installed(tmp_path)
    for run in (
        EdgeRun(code=1),
        EdgeRun(out=b"  \n"),
        EdgeRun(error=subprocess.TimeoutExpired("msedge", 60)),
        EdgeRun(error=OSError("cannot start")),
    ):
        with pytest.raises(SourceUnavailableError, match="edge"):
            Edge(tmp_path, [edge], run).dom("https://example.com")
    with pytest.raises(SourceUnavailableError, match="edge: not installed"):
        Edge(tmp_path, [tmp_path / "missing.exe"], EdgeRun()).dom("https://example.com")
