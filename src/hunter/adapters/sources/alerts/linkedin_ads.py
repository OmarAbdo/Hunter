"""The whole ad of a job a LinkedIn alert mail showed, from LinkedIn's public guest page for it:
`www.linkedin.com/jobs-guest/jobs/api/jobPosting/<job id>`, which logged-out visitors are shown.
The job id is all Hunter takes from the mail; its links, which can sign in as Omar, are never
opened, and no account is used. LinkedIn's robots.txt turns bots away, so the page is read with a
browser's identity, slowly. A job no longer accepting applications, or one LinkedIn doesn't know
any more (404), is gone."""

import re
from datetime import timedelta

from hunter.adapters.html_text import plain_text
from hunter.adapters.sources.reading import read_text
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.posting import Posting
from hunter.domain.pacing import PaceRule

API = "https://www.linkedin.com"
HOST = "www.linkedin.com"
PACE = PaceRule(min_gap=timedelta(seconds=8))  # it shows a sign-in wall to the hasty
BROWSER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36 Edg/157.0.0.0",
    "Accept-Language": "en",
}
AD_TEXT = re.compile(r'<div class="show-more-less-html__markup[^"]*"[^>]*>(.*?)</div>', re.S)
CLOSED = 'class="closed-job'  # "No longer accepting applications"


class LinkedInAds:
    def __init__(self, web: WebClient, api: str = API) -> None:
        self.web = web
        self.api = api

    def read(self, posting: Posting) -> str:
        url = f"{self.api}/jobs-guest/jobs/api/jobPosting/{posting.source.native_id}"
        page = read_text(self.web, url, None, BROWSER)
        if CLOSED in page:
            raise SourceUnavailableError(f"{url}: no longer accepting applications", gone=True)
        found = AD_TEXT.search(page)
        return plain_text(found[1]) if found else ""
