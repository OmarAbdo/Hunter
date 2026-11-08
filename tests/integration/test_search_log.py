from datetime import UTC, datetime, timedelta
from pathlib import Path

from hunter.adapters.storage.database import open_database
from hunter.adapters.storage.search_log import Searched, SearchLog

NOON = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
HOUR = timedelta(hours=1)


def test_every_search_is_counted_by_engine_and_outcome(tmp_path: Path) -> None:
    log = SearchLog(open_database(tmp_path / "hunter.db"))
    log.record(Searched("duckduckgo", '"N26" careers jobs', "captcha", 0, NOON - HOUR))
    log.record(Searched("duckduckgo", '"N26" careers jobs', "captcha", 0, NOON))
    log.record(Searched("duckduckgo", '"Zalando" careers jobs', "links", 10, NOON))
    log.record(Searched("bing", '"N26" careers jobs', "nothing", 0, NOON + HOUR))
    assert log.summary(NOON) == {
        "duckduckgo": {"captcha": 1, "links": 1},
        "bing": {"nothing": 1},
    }
    assert log.summary(NOON - HOUR)["duckduckgo"] == {"captcha": 2, "links": 1}
    assert log.count("duckduckgo", NOON) == 2
    assert log.count("bing", NOON + 2 * HOUR) == 0


def test_the_last_search_is_known_whichever_engine_made_it(tmp_path: Path) -> None:
    log = SearchLog(open_database(tmp_path / "hunter.db"))
    assert log.last() is None
    log.record(Searched("bing", "a", "failed", 0, NOON + HOUR))
    log.record(Searched("duckduckgo", "b", "links", 3, NOON))
    assert log.last() == NOON + HOUR
    found = log.database.execute("SELECT query, links FROM searches WHERE engine = 'duckduckgo'")
    assert found.fetchall() == [("b", 3)]


def test_a_query_is_known_as_searched_since_a_time(tmp_path: Path) -> None:
    log = SearchLog(open_database(tmp_path / "hunter.db"))
    log.record(Searched("duckduckgo", '"Europace" Fullstack Developer', "links", 10, NOON))
    assert log.searched('"Europace" Fullstack Developer', NOON - HOUR)
    assert not log.searched('"Europace" Fullstack Developer', NOON + HOUR)
    assert not log.searched('"Europace" Backend Developer', NOON - HOUR)
    log.record(Searched("bing", '"Europace" Backend Developer', "captcha", 0, NOON))
    assert not log.searched('"Europace" Backend Developer', NOON - HOUR)
