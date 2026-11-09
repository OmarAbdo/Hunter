from datetime import UTC, datetime, timedelta
from pathlib import Path

from hunter.adapters.storage.database import open_database
from hunter.adapters.storage.search_log import Searched, SearchLog
from hunter.domain.search_turns import EngineUse

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


def test_a_query_s_answers_since_a_time_are_counted(tmp_path: Path) -> None:
    """A captcha or a failure isn't an answer."""
    log = SearchLog(open_database(tmp_path / "hunter.db"))
    log.record(Searched("duckduckgo", '"Europace" Fullstack Developer', "links", 10, NOON))
    log.record(Searched("bing", '"Europace" Fullstack Developer', "nothing", 0, NOON + HOUR))
    log.record(Searched("brave", '"Europace" Fullstack Developer', "captcha", 0, NOON + HOUR))
    assert log.answers('"Europace" Fullstack Developer', NOON - HOUR) == 2
    assert log.answers('"Europace" Fullstack Developer', NOON + HOUR) == 1
    assert log.answers('"Europace" Backend Developer', NOON - HOUR) == 0


def test_each_engine_s_searches_since_a_time_come_oldest_first(tmp_path: Path) -> None:
    log = SearchLog(open_database(tmp_path / "hunter.db"))
    log.record(Searched("bing", "q", "captcha", 0, NOON))
    log.record(Searched("bing", "q", "links", 3, NOON - HOUR))
    log.record(Searched("duckduckgo", "q", "links", 3, NOON - 3 * HOUR))
    assert log.uses(["duckduckgo", "bing", "mojeek"], NOON - 2 * HOUR) == [
        EngineUse("duckduckgo"),
        EngineUse("bing", ((NOON - HOUR, "links"), (NOON, "captcha"))),
        EngineUse("mojeek"),
    ]
