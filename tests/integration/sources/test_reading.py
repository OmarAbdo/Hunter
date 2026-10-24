from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from hunter.adapters.sources.reading import employment_from, parsed_time, place_at, read_json
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import Employment

SourceApi = Callable[[str, str | None], str]


def test_an_answer_that_is_not_json_makes_the_source_unavailable(
    source_api: SourceApi, web: WebClient
) -> None:
    api = source_api("/jobs", "not-json.txt")
    with pytest.raises(SourceUnavailableError, match="not JSON"):
        read_json(web, f"{api}/jobs")


def test_a_board_that_is_not_there_is_gone(source_api: SourceApi, web: WebClient) -> None:
    with pytest.raises(SourceUnavailableError, match="HTTP 404") as raised:
        read_json(web, f"{source_api('/jobs', None)}/jobs")
    assert raised.value.gone


def test_times_are_read_as_sources_write_them() -> None:
    assert parsed_time("2026-08-13T10:31:57Z") == datetime(2026, 8, 13, 10, 31, 57, tzinfo=UTC)
    assert parsed_time("2026-10-05 13:25:03 UTC") == datetime(2026, 10, 5, 13, 25, 3, tzinfo=UTC)
    assert parsed_time(None) is None
    assert parsed_time("last Tuesday") is None


@pytest.mark.parametrize(
    ("text", "employment"),
    [
        ("Full-time", Employment.FULL_TIME),
        ("fulltime_permanent", Employment.FULL_TIME),
        ("Part time", Employment.PART_TIME),
        ("Intern (full-time)", Employment.INTERNSHIP),
        ("Freelance", Employment.CONTRACT),
        ("Temporary", Employment.TEMPORARY),
        ("Other", None),
        (None, None),
    ],
)
def test_employment_types_are_read_from_their_words(
    text: str | None, employment: Employment | None
) -> None:
    assert employment_from(text) is employment


def test_a_remote_place_is_open_to_its_country() -> None:
    assert place_at("Berlin, DE", Workplace.REMOTE) == Location(
        country="DE", city="Berlin", workplace=Workplace.REMOTE, remote_scope=frozenset({"DE"})
    )
    assert place_at("Berlin, DE", Workplace.HYBRID).remote_scope == frozenset()
