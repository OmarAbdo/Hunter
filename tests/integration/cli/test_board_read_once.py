from pathlib import Path

from hunter.adapters.cli.project import Project
from hunter.adapters.cli.sources import feeds_of
from hunter.adapters.storage.registry import Registry
from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.company import Company

BOARD = Board(ats="personio", slug="1komma5grad.de")


def test_a_board_two_companies_claim_is_read_once(tmp_path: Path) -> None:
    project = Project(tmp_path)
    registry = Registry(project.database())
    registry.save(Company(name="1KOMMA5°").with_board(BOARD))
    registry.save(Company(name="1KOMMA5° Heat GmbH").with_board(BOARD))
    assert [feed.name for feed in feeds_of(project, project.database())] == [BOARD.key]
