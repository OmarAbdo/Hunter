from hunter.adapters.sources.feed_table import APIS, FEEDS
from hunter.domain.discovery.boards import LINK_PATTERNS

NO_FEED = {"join"}  # JOIN publishes no job data; its jobs come by mail


def test_every_system_the_link_reader_knows_has_a_feed() -> None:
    known = {ats for ats, _, _ in LINK_PATTERNS}
    assert set(FEEDS) == known - NO_FEED


def test_every_feed_has_a_web_address() -> None:
    assert set(APIS) == set(FEEDS)
