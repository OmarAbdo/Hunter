from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from hunter.adapters.sources.reading import parsed_time, read_json
from hunter.adapters.web.client import WebClient
from hunter.application.ports import SourceUnavailableError

SourceApi = Callable[[str, str | None], str]


def test_an_answer_that_is_not_json_makes_the_source_unavailable(
    source_api: SourceApi, web: WebClient
) -> None:
    api = source_api("/jobs", "not-json.txt")
    with pytest.raises(SourceUnavailableError, match="not JSON"):
        read_json(web, f"{api}/jobs")


def test_times_are_read_as_sources_write_them() -> None:
    assert parsed_time("2026-08-13T10:31:57Z") == datetime(2026, 8, 13, 10, 31, 57, tzinfo=UTC)
    assert parsed_time(None) is None
    assert parsed_time("last Tuesday") is None
