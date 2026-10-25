import io
import urllib.error
from datetime import UTC, datetime
from email.message import Message

from hunter.adapters.web_answers import decoded, retry_after

NOW = datetime(2026, 10, 25, 18, 0, tzinfo=UTC)


def limited(value: str | None) -> urllib.error.HTTPError:
    headers = Message()
    if value is not None:
        headers["Retry-After"] = value
    return urllib.error.HTTPError("https://example.com", 429, "slow down", headers, io.BytesIO())


def test_a_pause_in_seconds_is_taken_as_it_is() -> None:
    assert retry_after(limited("75335"), NOW) == 75335.0


def test_a_pause_as_a_time_to_come_back_counts_from_now() -> None:
    assert retry_after(limited("Sun, 25 Oct 2026 18:05:00 GMT"), NOW) == 300.0
    assert retry_after(limited("Sun, 25 Oct 2026 17:00:00 GMT"), NOW) == 0.0


def test_no_pause_or_one_that_cannot_be_read_is_none() -> None:
    assert retry_after(limited(None), NOW) is None
    assert retry_after(limited("soon"), NOW) is None


def test_text_comes_in_the_encoding_the_site_names() -> None:
    assert decoded("für".encode("latin-1"), "latin-1") == "für"
