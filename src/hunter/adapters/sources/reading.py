"""What every source adapter needs to read a source: its answer as JSON, with a failure of any kind
turned into SourceUnavailableError, and times as sources write them."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from hunter.adapters.web.client import WebClient, WebError
from hunter.application.ports import SourceUnavailableError


def read_json(web: WebClient, url: str, params: Mapping[str, str] | None = None) -> Any:
    try:
        return web.get_json(url, params)
    except WebError as error:
        raise SourceUnavailableError(str(error)) from error
    except ValueError as error:
        raise SourceUnavailableError(f"{url}: not JSON ({error})") from error


def parsed_time(text: str | None) -> datetime | None:
    """An ISO 8601 time, or None when there is none or it can't be read."""
    try:
        return datetime.fromisoformat(text) if text else None
    except ValueError:
        return None
