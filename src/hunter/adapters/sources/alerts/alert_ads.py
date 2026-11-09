"""The whole ads of jobs only a job-alert mail showed (StepStone, XING): the mail's link is a
click-tracking redirect, and the list in the mail has no ad.

The link's first hop is read without following it, and it names the job's public page. On
StepStone that hop is often a magic link that would sign in as the inbox's owner, and on XING it is
the login page; both carry the job's address inside (`returnUrl`, `dest_url`), which is taken from
there. The sign-in hop itself is never opened. The public page is read logged out, through
headless Edge, since both sites turn plain requests away. Its schema.org `JobPosting` holds the ad;
a page that says the job is no longer there makes it gone. Alert jobs are taken down within days,
so they're read in the run their mail arrives in. Adzuna's details pages are read the same way."""

import re
import sqlite3
import urllib.request
from collections.abc import Callable
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

from hunter.adapters.edge_search import Edge
from hunter.adapters.sources.reading import JobPageAds, ad_on_page
from hunter.adapters.sources.searches.employer_search import employer_readers
from hunter.adapters.storage import registry, search_log
from hunter.application.ports import AdReader, SourceUnavailableError
from hunter.domain.discovery.posting import Posting

STEPSTONE_JOB = re.compile(r"/stellenangebote-[^/]*--(\d{6,9})-inline\.html$")
AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
TIMEOUT = 30


class NotFollowed(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_: object, **__: object) -> None:
        return None


def first_hop(url: str) -> str | None:
    """Where the link redirects to, read without going there."""
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    try:
        urllib.request.build_opener(NotFollowed).open(request, timeout=TIMEOUT).close()
    except urllib.request.HTTPError as error:
        return error.headers.get("Location")
    except OSError:
        return None
    return None


def job_page(hop: str | None) -> str | None:
    """The public page of the job a first hop names, without its tracking; none when it names
    no job."""
    if not hop:
        return None
    query = parse_qs(urlsplit(hop).query)
    inner = (query.get("returnUrl") or query.get("dest_url") or [""])[0]
    target = urlsplit(urljoin(hop, inner) if inner else hop)
    found = STEPSTONE_JOB.search(target.path)
    if target.netloc.endswith("stepstone.de") and found:
        # The address needs a slug, any slug: without one StepStone answers 404.
        return f"https://www.stepstone.de/stellenangebote--job--{found[1]}-inline.html"
    if target.netloc == "www.xing.com" and target.path.startswith("/jobs/"):
        return f"https://www.xing.com{target.path}"
    return None


class AlertPageAds:
    def __init__(self, hop: Callable[[str], str | None], page: Callable[[str], str]) -> None:
        self.hop = hop
        self.page = page

    def read(self, posting: Posting) -> str:
        target = job_page(self.hop(posting.url or ""))
        if target is None:
            raise SourceUnavailableError(f"{posting.source.source}: the link names no job page")
        return ad_on_page(self.page(target), target)


def edge_readers(
    profile: Path, database: sqlite3.Connection, plain: Callable[[str], str]
) -> dict[str, AdReader]:
    """The sources whose pages only Edge can read, with a profile of their own: the alert jobs,
    Adzuna's details pages, which answer plain requests with 403, and the employer's own ad for
    the jobs whose board can't be read at all (searches/employer_search.py), whose candidate
    pages are read with `plain` first."""
    edge = Edge(profile)
    alerts = AlertPageAds(first_hop, edge.dom)
    return {
        "stepstone-alert": alerts,
        "xing-alert": alerts,
        "adzuna": JobPageAds(edge.dom),
        **employer_readers(
            edge, search_log.SearchLog(database), registry.Registry(database).adopt, plain
        ),
    }
