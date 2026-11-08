from datetime import UTC, datetime, timedelta

from hunter.domain.search_turns import EngineUse, Turns, next_engines

NOW = datetime(2026, 11, 8, 18, 0, tzinfo=UTC)
MINUTE = timedelta(minutes=1)
TURNS = Turns(per_hour=3, rest=timedelta(hours=1), longest_rest=timedelta(hours=8))


def used(name: str, *searches: tuple[int, str]) -> EngineUse:
    """An engine's searches, each so many minutes ago, with its outcome; the oldest first."""
    return EngineUse(
        name, tuple((NOW - minutes * MINUTE, outcome) for minutes, outcome in searches)
    )


def test_the_engine_used_longest_ago_takes_the_next_search() -> None:
    uses = [used("duckduckgo", (2, "links")), used("bing", (30, "links")), used("mojeek")]
    assert next_engines(uses, NOW, TURNS) == ["mojeek", "bing", "duckduckgo"]


def test_an_engine_at_its_share_of_the_last_hour_waits() -> None:
    busy = used("duckduckgo", (90, "links"), (61, "links"), (50, "links"), (40, "links"))
    full = used("bing", (50, "links"), (40, "links"), (30, "links"))
    assert next_engines([busy, full], NOW, TURNS) == ["duckduckgo"]


def test_an_engine_that_showed_a_captcha_rests_twice_as_long_after_each_in_a_row() -> None:
    once = used("duckduckgo", (90, "links"), (59, "captcha"))
    assert next_engines([once], NOW, TURNS) == []
    assert next_engines([once], NOW + 2 * MINUTE, TURNS) == ["duckduckgo"]
    twice = used("bing", (150, "captcha"), (110, "captcha"))
    assert next_engines([twice], NOW, TURNS) == []
    assert next_engines([twice], NOW + 11 * MINUTE, TURNS) == ["bing"]


def test_a_rest_never_lasts_longer_than_the_longest() -> None:
    """Six captchas in a row would mean 32 hours; the longest rest is 8."""
    many = used("google", *((100 - step, "captcha") for step in range(6)))
    rested = NOW - 95 * MINUTE + 8 * timedelta(hours=1)
    assert next_engines([many], rested - MINUTE, TURNS) == []
    assert next_engines([many], rested + MINUTE, TURNS) == ["google"]


def test_an_answer_after_a_captcha_ends_the_rest() -> None:
    answered = used("bing", (100, "captcha"), (20, "links"))
    assert next_engines([answered], NOW, TURNS) == ["bing"]


def test_an_engine_whose_answer_was_unreadable_rests_too() -> None:
    """A page with neither results nor a challenge it's known by is most often one in disguise."""
    unreadable = used("swisscows", (90, "links"), (30, "failed"))
    assert next_engines([unreadable], NOW, TURNS) == []
