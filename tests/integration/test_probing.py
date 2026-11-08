import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hunter.adapters.edge_search import Pace
from hunter.adapters.probing import OneSearchAtATime, searches_line
from hunter.adapters.storage.database import open_database
from hunter.adapters.storage.search_log import SearchLog, Searched

REPOSITORY = Path(__file__).resolve().parents[2]
SAVED = REPOSITORY / "tests/fixtures/sources"
ZALANDO = {
    engine: (SAVED / f"edge-search-{engine}-zalando.html").read_text(encoding="utf-8")
    for engine in ("duckduckgo", "bing")
}
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


def test_probing_threads_search_one_at_a_time_and_every_search_is_logged(tmp_path: Path) -> None:
    """Probing runs on several threads; each search is made alone and logged on a connection of
    its own, since a connection belongs to the thread that opened it. The engines take turns."""
    at_once: list[int] = []
    searching = [0]

    def browse(url: str) -> str:
        searching[0] += 1
        at_once.append(searching[0])
        searching[0] -= 1
        return ZALANDO["bing" if "bing.com" in url else "duckduckgo"]

    path = tmp_path / "hunter.db"
    search = OneSearchAtATime(browse, lambda: open_database(path), Pace(sleep=lambda _: None))
    found: list[list[str]] = []
    threads = [threading.Thread(target=lambda: found.append(search.links("Zalando"))) for _ in "ab"]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert at_once == [1, 1]
    assert [len(links) > 0 for links in found] == [True, True]
    assert SearchLog(open_database(path)).summary(NOW - timedelta(days=1)) == {
        "duckduckgo": {"links": 1},
        "bing": {"links": 1},
    }


def test_the_searches_are_summed_up_by_engine_and_outcome(tmp_path: Path) -> None:
    database = open_database(tmp_path / "hunter.db")
    log = SearchLog(database)
    for engine, outcome in [("duckduckgo", "links"), ("duckduckgo", "captcha"), ("bing", "links")]:
        log.record(Searched(engine, "N26", outcome, 3, NOW))
    assert searches_line(database, NOW - timedelta(hours=1)) == (
        "Web searches: duckduckgo links 1, captcha 1; bing links 1"
    )
    assert searches_line(database, NOW + timedelta(hours=1)) == "Web searches: none"
