from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.probing import board_candidates, slugs


def test_slugs_come_from_the_name_without_its_legal_form() -> None:
    assert slugs("Bartko & Reher GmbH & Co. KG") == [
        "bartkoandreher",
        "bartko-and-reher",
        "bartkoreher",
    ]
    assert slugs("N26 GmbH") == ["n26"]
    assert slugs("Redcare Pharmacy") == ["redcarepharmacy", "redcare-pharmacy"]


def test_a_name_without_letters_has_no_slugs() -> None:
    assert slugs("GmbH") == []


def test_every_guessable_system_is_tried_with_every_slug() -> None:
    boards = board_candidates("Redcare Pharmacy")
    assert Board(ats="greenhouse", slug="redcarepharmacy") in boards
    assert Board(ats="ashby", slug="redcare-pharmacy") in boards
    assert Board(ats="personio", slug="redcarepharmacy.de") in boards
    assert Board(ats="personio", slug="redcare-pharmacy.com") in boards
    assert Board(ats="smartrecruiters", slug="Redcare-Pharmacy") in boards
    assert Board(ats="softgarden", slug="redcarepharmacy") in boards
    assert Board(ats="onlyfy", slug="redcare-pharmacy") in boards
    assert Board(ats="smartrecruiters", slug="RedcarePharmacy") in boards
    assert not [board for board in boards if board.ats == "workday"]


def test_the_most_likely_board_comes_first() -> None:
    assert board_candidates("N26")[0] == Board(ats="greenhouse", slug="n26")


def test_names_too_long_for_a_web_address_give_no_board() -> None:
    long_name = "Berufliche Schulen Potsdam der ASG Anerkannten Schulgesellschaft mbH"
    assert all(len(slug) <= 63 for slug in slugs(long_name))
    assert all(len(board.slug.split(".")[0]) <= 63 for board in board_candidates(long_name))


def test_workable_is_not_guessed() -> None:
    """Workable allows few requests a day, and blocked Hunter for 21 hours after a day of
    guessing (2026-10-25). Its boards come from links."""
    assert all(board.ats != "workable" for board in board_candidates("Redcare Pharmacy"))
