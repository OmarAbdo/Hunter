from datetime import UTC, datetime

from hunter.application.ports import SourceUnavailableError
from hunter.application.probe import ProbeResult, ProbeStores, probe
from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.company import Company, FeedStatus

NOW = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)


class Boards:
    """Answers whether a board exists, from the boards it knows; `down` can't be reached."""

    def __init__(self, *existing: Board, down: bool = False) -> None:
        self.existing = set(existing)
        self.down = down
        self.asked: list[Board] = []

    def exists(self, board: Board) -> bool:
        self.asked.append(board)
        if self.down:
            raise SourceUnavailableError(f"{board.key}: no answer")
        return board in self.existing


class Companies:
    def __init__(self) -> None:
        self.saved: dict[str, Company] = {}

    def get(self, key: str) -> Company | None:
        return self.saved.get(key)

    def save(self, company: Company) -> None:
        self.saved[company.key] = company

    def owner_of(self, board: Board) -> Company | None:
        return None


class Log:
    def __init__(self) -> None:
        self.probed: dict[str, datetime] = {}

    def record(self, company_key: str, probed_at: datetime) -> None:
        self.probed[company_key] = probed_at


def stores() -> ProbeStores:
    return ProbeStores(companies=Companies(), log=Log())


def test_the_first_board_that_exists_is_added_as_live() -> None:
    kept = stores()
    found = Board(ats="ashby", slug="n26")
    [result] = probe([Company(name="N26")], Boards(found), kept, NOW)
    assert result == ProbeResult(company="N26", board=found)
    company = kept.companies.get("n26")
    assert company is not None
    assert company.feed_status(found) is FeedStatus.LIVE


def test_probing_stops_at_the_first_board_found() -> None:
    boards = Boards(Board(ats="greenhouse", slug="n26"), Board(ats="ashby", slug="n26"))
    list(probe([Company(name="N26")], boards, stores(), NOW))
    assert boards.asked == [Board(ats="greenhouse", slug="n26")]


def test_a_company_without_a_board_is_still_logged_as_probed() -> None:
    kept = stores()
    [result] = probe([Company(name="N26")], Boards(), kept, NOW)
    assert result == ProbeResult(company="N26", board=None)
    assert isinstance(kept.log, Log)
    assert kept.log.probed == {"n26": NOW}
    assert kept.companies.get("n26") is None


def test_a_company_that_could_not_be_probed_is_tried_again_next_time() -> None:
    kept = stores()
    [result] = probe([Company(name="N26")], Boards(down=True), kept, NOW)
    assert result.board is None
    assert result.error == "greenhouse:n26: no answer"
    assert isinstance(kept.log, Log)
    assert kept.log.probed == {}
