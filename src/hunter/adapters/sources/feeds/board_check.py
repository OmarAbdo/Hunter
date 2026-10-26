"""Checking a guessed board: it's the company's when it answers with jobs and the jobs name the
company, as far as the feed names one. A guess like `delivery` could otherwise find another
company's board. A board that isn't there (404) or has no jobs doesn't count."""

from collections.abc import Mapping

from hunter.adapters.sources.feed_table import FEEDS
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.identity import company_key


class FeedCheck:
    def __init__(self, web: WebClient, apis: Mapping[str, str | tuple[str, ...]]) -> None:
        self.web = web
        self.apis = apis

    def exists(self, board: Board, company: str) -> bool:
        if board.ats not in FEEDS:  # a system Hunter can't read (JOIN), so nothing to check
            return False
        feed = FEEDS[board.ats](self.web, board.slug, company, api=self.apis[board.ats])
        try:
            postings = feed.fetch()
        except SourceUnavailableError as error:
            if error.gone:
                return False
            raise
        return any(fits(posting.company, company) for posting in postings)


def fits(named: str, company: str) -> bool:
    """'N26 GmbH' fits 'N26'; '1KOMMA5° Heat GmbH' fits '1KOMMA5°'; 'Zalando' doesn't fit 'N26'."""
    named_key, company_name_key = company_key(named), company_key(company)
    shorter, longer = sorted((named_key, company_name_key), key=len)
    return bool(shorter) and shorter in longer
