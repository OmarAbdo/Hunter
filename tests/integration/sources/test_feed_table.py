from datetime import timedelta

from hunter.adapters.sources.feed_table import APIS, FEEDS, PACES
from hunter.domain.discovery.boards import LINK_PATTERNS

NO_FEED = {"join"}  # JOIN publishes no job data; its jobs come by mail


def test_every_system_the_link_reader_knows_has_a_feed() -> None:
    known = {ats for ats, _, _ in LINK_PATTERNS}
    assert set(FEEDS) == known - NO_FEED


def test_every_feed_has_a_web_address() -> None:
    assert set(APIS) == set(FEEDS)


def test_workable_is_read_slowly_enough_not_to_be_refused() -> None:
    """Workable answered 429 after about 16 requests a second apart (2026-10-25); 12 three
    seconds apart went through."""
    assert PACES["apply.workable.com"].min_gap >= timedelta(seconds=3)
