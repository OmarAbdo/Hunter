import pytest

from hunter.adapters.sources.searches.keyed import keeping_keys_out, without_tracking
from hunter.application.ports import SourceUnavailableError


def test_an_error_keeps_its_meaning_without_the_keys() -> None:
    def failing() -> None:
        raise SourceUnavailableError("api.example.com: HTTP 404 for /api/s3cret?key=k3y", gone=True)

    with pytest.raises(SourceUnavailableError) as raised:
        keeping_keys_out(failing, ["s3cret", "k3y"])
    assert str(raised.value) == "api.example.com: HTTP 404 for /api/<key>?key=<key>"
    assert raised.value.gone
    assert raised.value.__cause__ is None  # the original error, with the keys, isn't kept


def test_a_read_that_works_is_given_back() -> None:
    assert keeping_keys_out(lambda: 42, ["s3cret"]) == 42


def test_a_link_loses_its_query() -> None:
    link = "https://www.adzuna.de/land/ad/1?se=x&utm_source=app-id"
    assert without_tracking(link) == "https://www.adzuna.de/land/ad/1"
