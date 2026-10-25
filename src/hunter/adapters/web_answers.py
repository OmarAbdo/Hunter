"""What a site's answer means to Hunter: its text, the pause it asks for, and the failures that mean
no answer came."""

import http.client
import urllib.error
from datetime import datetime
from email.utils import parsedate_to_datetime

NO_ANSWER = (OSError, http.client.HTTPException)  # no connection, a hang-up, a cut-off answer


def decoded(body: bytes, charset: str | None) -> str:
    """Text in the encoding the site names, else UTF-8. Letters that don't fit are replaced, since
    many small sites send Latin-1 without saying so."""
    try:
        return body.decode(charset or "utf-8", errors="replace")
    except LookupError:  # an encoding Python doesn't know
        return body.decode("utf-8", errors="replace")


def retry_after(error: urllib.error.HTTPError, now: datetime) -> float | None:
    """The pause a Retry-After header asks for, in seconds: given as seconds, or as the time to
    come back."""
    value = (error.headers.get("Retry-After") or "").strip()
    if value.isdigit():
        return float(value)
    try:
        until = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, (until - now).total_seconds())
