from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.company import Company, FeedStatus

GREENHOUSE = Board(ats="greenhouse", slug="nextcloud")
ASHBY = Board(ats="ashby", slug="nextcloud")


def test_a_company_is_known_by_its_normalised_name() -> None:
    assert Company(name="Nextcloud GmbH").key == "nextcloud"


def test_a_new_board_starts_unchecked() -> None:
    company = Company(name="Nextcloud").with_board(GREENHOUSE)
    assert company.feed_status(GREENHOUSE) is FeedStatus.UNCHECKED


def test_boards_are_added_once() -> None:
    company = Company(name="Nextcloud").with_board(GREENHOUSE).with_board(GREENHOUSE)
    assert company.boards == (GREENHOUSE,)


def test_a_checked_board_keeps_its_status() -> None:
    company = Company(name="Nextcloud").with_board(GREENHOUSE).checked(GREENHOUSE, FeedStatus.LIVE)
    assert company.feed_status(GREENHOUSE) is FeedStatus.LIVE


def test_feeds_to_read_leave_out_boards_that_are_gone() -> None:
    company = (
        Company(name="Nextcloud")
        .with_board(GREENHOUSE)
        .with_board(ASHBY)
        .checked(GREENHOUSE, FeedStatus.GONE)
    )
    assert company.feeds_to_read() == (ASHBY,)


def test_the_first_website_found_is_kept() -> None:
    company = Company(name="Baier GmbH").with_website("http://www.baier.de")
    assert company.with_website("http://baier-werbetechnik.de").website == "http://www.baier.de"
    assert Company(name="Baier GmbH").website is None
