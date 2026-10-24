"""A company in the registry: known by its normalised name, with the boards where it posts jobs
and what Hunter found when it last read each one."""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import Enum

from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.identity import company_key


class FeedStatus(Enum):
    UNCHECKED = "unchecked"
    LIVE = "live"
    EMPTY = "empty"
    GONE = "gone"


@dataclass(frozen=True)
class Company:
    name: str
    feeds: Mapping[Board, FeedStatus] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return company_key(self.name)

    @property
    def boards(self) -> tuple[Board, ...]:
        return tuple(self.feeds)

    def feed_status(self, board: Board) -> FeedStatus:
        return self.feeds[board]

    def with_board(self, board: Board) -> "Company":
        if board in self.feeds:
            return self
        return replace(self, feeds={**self.feeds, board: FeedStatus.UNCHECKED})

    def checked(self, board: Board, status: FeedStatus) -> "Company":
        return replace(self, feeds={**self.feeds, board: status})

    def feeds_to_read(self) -> tuple[Board, ...]:
        """Every board except the ones that are gone (a 404 or 410 when last read)."""
        return tuple(board for board, status in self.feeds.items() if status is not FeedStatus.GONE)
