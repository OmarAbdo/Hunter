from pathlib import Path

from hunter.adapters.database import open_database
from hunter.adapters.registry import Registry
from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.company import Company, FeedStatus

GREENHOUSE = Board(ats="greenhouse", slug="nextcloud")
ASHBY = Board(ats="ashby", slug="nextcloud")


def test_a_saved_company_comes_back_with_its_boards(tmp_path: Path) -> None:
    registry = Registry(open_database(tmp_path / "hunter.db"))
    company = (
        Company(name="Nextcloud GmbH").with_board(GREENHOUSE).checked(GREENHOUSE, FeedStatus.LIVE)
    )
    registry.save(company)
    assert registry.get("nextcloud") == company


def test_an_unknown_company_is_none(tmp_path: Path) -> None:
    assert Registry(open_database(tmp_path / "hunter.db")).get("nextcloud") is None


def test_saving_again_replaces_the_company(tmp_path: Path) -> None:
    registry = Registry(open_database(tmp_path / "hunter.db"))
    registry.save(Company(name="Nextcloud").with_board(GREENHOUSE))
    registry.save(Company(name="Nextcloud").with_board(GREENHOUSE).with_board(ASHBY))
    assert registry.get("nextcloud") == Company(name="Nextcloud").with_board(GREENHOUSE).with_board(
        ASHBY
    )
    assert len(registry.all()) == 1


def test_a_board_names_its_company(tmp_path: Path) -> None:
    registry = Registry(open_database(tmp_path / "hunter.db"))
    registry.save(Company(name="Nextcloud").with_board(GREENHOUSE))
    assert registry.owner_of(GREENHOUSE) == Company(name="Nextcloud").with_board(GREENHOUSE)
    assert registry.owner_of(ASHBY) is None


def test_all_companies_in_name_order(tmp_path: Path) -> None:
    registry = Registry(open_database(tmp_path / "hunter.db"))
    registry.save(Company(name="Zalando"))
    registry.save(Company(name="Ashby"))
    assert [company.name for company in registry.all()] == ["Ashby", "Zalando"]
