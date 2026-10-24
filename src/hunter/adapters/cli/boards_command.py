"""`boards add <link>...`: puts the job boards the links point at in the company registry."""

from collections.abc import Sequence
from typing import TextIO

from hunter.adapters.cli.project import Project
from hunter.adapters.registry import Registry
from hunter.domain.discovery.boards import board_from_link
from hunter.domain.discovery.company import Company
from hunter.domain.discovery.identity import company_key


def add_boards(project: Project, links: Sequence[str], company: str | None, out: TextIO) -> int:
    registry = Registry(project.database())
    for link in links:
        board = board_from_link(link)
        if board is None:
            out.write(f"{link} names no job board Hunter knows\n")
            return 1
        name = company or board.slug
        owner = registry.owner_of(board) or registry.get(company_key(name)) or Company(name=name)
        registry.save(owner.with_board(board))
        out.write(f"{owner.name}: {board.key}\n")
    return 0
