"""A company's careers pages, for probing (docs/discovery.md, "Finding a company's board"): the
links on its website's home page, and on the pages of its own site the home page calls careers
("Karriere", "Jobs", "Careers"). Links to job boards are found there: in anchors, in the scripts and
frames that embed a board, and written into the page's code. A site that can't be read has no
links; a careers page that can't be read gives the home page's."""

import re
from urllib.parse import urljoin, urlsplit

from hunter.adapters.web_client import WebClient, WebError

CAREERS = re.compile(r"karriere|career|jobs|stellen|join-?us|arbeiten-bei|work-with-us", re.I)
MOST_CAREERS_PAGES = 2
WRITTEN_LINKS = re.compile(r"""https?://[^\s"'<>\\)]+""")
ATTRIBUTE_LINKS = re.compile(r"""(?:href|src)=["']([^"'#]+)["']""", re.I)


class CareersPages:
    def __init__(self, web: WebClient) -> None:
        self.web = web

    def links(self, website: str) -> list[str]:
        home = self._read(website)
        found = links_in(home, website)
        careers = [link for link in found if own_page(link, website) and CAREERS.search(link)]
        for page in list(dict.fromkeys(careers))[:MOST_CAREERS_PAGES]:
            found += links_in(self._read(page), page)
        return list(dict.fromkeys(found))

    def _read(self, url: str) -> str:
        try:
            return self.web.get_page(url)
        except WebError:
            return ""


def links_in(page: str, address: str) -> list[str]:
    attributes = [urljoin(address, link) for link in ATTRIBUTE_LINKS.findall(page)]
    return [*attributes, *WRITTEN_LINKS.findall(page)]


def own_page(link: str, website: str) -> bool:
    """On the company's own site: its host, or a host under it (jobs.acme.com for acme.com)."""
    host = urlsplit(website).netloc.lower().removeprefix("www.")
    link_host = urlsplit(link).netloc.lower()
    return link_host == host or link_host.endswith(f".{host}") or link_host == f"www.{host}"
