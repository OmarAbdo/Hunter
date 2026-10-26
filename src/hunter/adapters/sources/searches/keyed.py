"""What keyed search sources share: their keys stay out of everything a run prints, and their job
links lose the query that tracks the click (and can carry the key)."""

from collections.abc import Callable, Iterable
from urllib.parse import urlsplit, urlunsplit

from hunter.application.ports import SourceUnavailableError

HIDDEN = "<key>"


def keeping_keys_out[Result](read: Callable[[], Result], secrets: Iterable[str]) -> Result:
    """`read()`, with any key taken out of the error it raises: errors name the address asked,
    and a keyed source's address holds its key."""
    try:
        return read()
    except SourceUnavailableError as error:
        message = str(error)
        for secret in secrets:
            message = message.replace(secret, HIDDEN)
        raise SourceUnavailableError(message, gone=error.gone) from None


def without_tracking(link: str) -> str:
    parts = urlsplit(link)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
