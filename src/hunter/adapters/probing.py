"""What `boards probe` asks the outside world with (docs/sources.md): each system's board check,
the companies' careers pages, and, last, a web search through Edge."""

import sqlite3
import threading
from collections.abc import Callable, Mapping
from contextlib import closing
from datetime import datetime
from pathlib import Path

from hunter.adapters.edge_search import Edge, EdgeSearch, Pace
from hunter.adapters.sources.feed_table import APIS, PACE, PACES
from hunter.adapters.sources.feeds import board_check, careers_pages
from hunter.adapters.storage.holds import kept_pacing
from hunter.adapters.storage.search_log import SearchLog
from hunter.adapters.web_client import WebClient

Connect = Callable[[], sqlite3.Connection]


class OneSearchAtATime:
    """The web search for probing, which runs on several threads: one search at a time, so the
    pace holds, each logged on a connection of its own, since a connection belongs to the thread
    that opened it."""

    def __init__(self, browse: Callable[[str], str], connect: Connect, pace: Pace | None = None):
        self.browse, self.connect, self.pace = browse, connect, pace
        self.lock = threading.Lock()

    def links(self, query: str) -> list[str]:
        with self.lock, closing(self.connect()) as database:
            return EdgeSearch(self.browse, SearchLog(database), self.pace).links(query)


def probe_tools(
    connect: Connect, apis: Mapping[str, str], profile: Path
) -> tuple[board_check.FeedCheck, careers_pages.CareersPages, OneSearchAtATime]:
    """The board check, the careers pages and the web search. `profile` is Edge's own folder for
    Hunter, apart from Omar's."""
    web = WebClient(kept_pacing(PACES, PACE, connect))
    check = board_check.FeedCheck(web, {**APIS, **apis})
    return check, careers_pages.CareersPages(web), OneSearchAtATime(Edge(profile).dom, connect)


def searches_line(database: sqlite3.Connection, since: datetime) -> str:
    """How the web searches since `since` went, by engine: how often each brought links, nothing,
    a captcha, or failed."""
    summary = SearchLog(database).summary(since)
    engines = [
        engine + " " + ", ".join(f"{outcome} {count}" for outcome, count in outcomes.items())
        for engine, outcomes in summary.items()
    ]
    return "Web searches: " + ("; ".join(engines) or "none")
