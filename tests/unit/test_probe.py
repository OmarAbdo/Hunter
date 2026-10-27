from datetime import UTC, datetime

from hunter.application.ports import SourceUnavailableError
from hunter.application.probe import (
    ProbeResult,
    ProbeStores,
    find_board,
    kept,
    probe,
    probe_marks,
)
from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.company import Company, FeedStatus

NOW = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)


class Boards:
    """Answers whether a board exists, from the boards it knows; `down` can't be reached."""

    def __init__(self, *existing: Board, down: bool = False) -> None:
        self.existing = set(existing)
        self.down = down
        self.asked: list[Board] = []

    def exists(self, board: Board, company: str) -> bool:
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


def test_finding_a_board_gives_the_board_none_or_why_it_could_not_tell() -> None:
    found = Board(ats="ashby", slug="n26")
    assert find_board(Company(name="N26"), Boards(found)) == found
    assert find_board(Company(name="N26"), Boards()) is None
    could_not = find_board(Company(name="N26"), Boards(down=True))
    assert isinstance(could_not, SourceUnavailableError)


class OwnedBoards(Companies):
    def __init__(self, owner: Company) -> None:
        super().__init__()
        self.owner = owner

    def owner_of(self, board: Board) -> Company | None:
        return self.owner if board in self.owner.feeds else None


def test_a_board_another_company_owns_is_not_given_to_a_second_one() -> None:
    board = Board(ats="personio", slug="zvoove.de")
    companies = OwnedBoards(Company(name="zvoove Software Germany GmbH").with_board(board))
    kept_ = ProbeStores(companies=companies, log=Log())
    [result] = probe([Company(name="zvoove")], Boards(board), kept_, NOW)
    assert result.board == board
    assert companies.saved == {}


class Pages:
    """The links on each website's pages, as a careers-page reader would find them."""

    def __init__(self, links: dict[str, list[str]]) -> None:
        self.links_by_site = links

    def links(self, website: str) -> list[str]:
        return self.links_by_site.get(website, [])


ACME = Company(name="Acme", website="https://acme.example")
SITE = Pages(
    {"https://acme.example": ["https://acme.example/team", "https://jobs.ashbyhq.com/acme"]}
)


def test_a_board_the_company_s_website_links_to_is_tried_first() -> None:
    boards = Boards(Board(ats="ashby", slug="acme"), Board(ats="greenhouse", slug="acme"))
    assert find_board(ACME, boards, SITE) == Board(ats="ashby", slug="acme")
    assert boards.asked == [Board(ats="ashby", slug="acme")]


def test_without_a_board_on_its_site_a_company_s_boards_are_still_guessed() -> None:
    boards = Boards(Board(ats="greenhouse", slug="acme"))
    assert find_board(ACME, boards, Pages({})) == Board(ats="greenhouse", slug="acme")


def test_a_company_probed_with_its_website_is_marked_so() -> None:
    """A company probed before it had a website is probed once more when it gains one."""
    kept_stores = stores()
    kept(ACME, find_board(ACME, Boards(), SITE), kept_stores, NOW)
    assert isinstance(kept_stores.log, Log)
    assert set(kept_stores.log.probed) == set(probe_marks(ACME)) == {"acme", "acme website"}
    assert probe_marks(Company(name="Acme")) == ["acme"]


class Search:
    """A web search that gives the same links for every query, and remembers what it was asked."""

    def __init__(self, *links: str, down: bool = False) -> None:
        self.found = list(links)
        self.down = down
        self.queries: list[str] = []

    def links(self, query: str) -> list[str]:
        self.queries.append(query)
        if self.down:
            raise SourceUnavailableError("search: no answer")
        return self.found


LABS = Board(ats="ashby", slug="acme-labs")


def results() -> Search:
    return Search(
        "https://acme.example/about",
        "https://jobs.lever.co/acme-old",
        "https://jobs.ashbyhq.com/acme-labs/1234",
        "https://jobs.ashbyhq.com/acme-labs",
        "https://boards.greenhouse.io/acme-two",
    )


def test_without_a_board_elsewhere_the_web_is_searched_for_one() -> None:
    boards = Boards(LABS, Board(ats="greenhouse", slug="acme-two"))
    search = results()
    assert find_board(Company(name="Acme"), boards, search=search) == LABS
    assert search.queries == ['"Acme" careers jobs']
    assert boards.asked[-2:] == [Board(ats="lever", slug="acme-old"), LABS]  # in result order


def test_the_web_is_not_searched_when_a_board_was_found_otherwise() -> None:
    search = results()
    assert find_board(ACME, Boards(Board(ats="ashby", slug="acme")), SITE, search)
    assert find_board(ACME, Boards(Board(ats="lever", slug="acme")), Pages({}), search)
    assert search.queries == []


def test_search_results_naming_no_board_that_exists_find_none() -> None:
    boards = Boards()
    assert find_board(Company(name="Acme"), boards, search=Search("https://acme.example")) is None
    assert find_board(Company(name="Acme"), boards, search=results()) is None
    assert boards.asked.count(LABS) == 1  # a board named twice is tried once


def test_a_board_already_tried_is_not_tried_again_from_the_search() -> None:
    boards = Boards()
    find_board(ACME, boards, SITE, Search("https://jobs.ashbyhq.com/acme"))
    assert boards.asked.count(Board(ats="ashby", slug="acme")) == 1
    assert len(boards.asked) == len(set(boards.asked))


def test_a_search_that_fails_says_why_the_board_could_not_be_found() -> None:
    found = find_board(Company(name="Acme"), Boards(), search=Search(down=True))
    assert isinstance(found, SourceUnavailableError)
    assert str(found) == "search: no answer"
