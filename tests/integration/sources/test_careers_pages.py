from collections.abc import Callable, Mapping

from hunter.adapters.sources.feeds.careers_pages import CareersPages
from hunter.adapters.web_client import WebClient

Pages = Callable[[Mapping[str, str]], str]


def test_links_come_from_the_home_page_and_its_careers_pages(
    source_pages: Pages, web: WebClient
) -> None:
    site = source_pages({"/": "careers-home.html", "/karriere": "careers-page.html"})
    links = CareersPages(web).links(site)
    assert "https://boards.greenhouse.io/embed/job_board?for=acme" in links  # on the careers page
    assert "https://www.linkedin.com/company/acme" in links  # on the home page
    assert f"{site}/karriere" in links


def test_careers_pages_on_other_sites_are_not_followed(source_pages: Pages, web: WebClient) -> None:
    """The home page links to a job board's careers page too; only the company's own are read."""
    site = source_pages({"/": "careers-home.html"})
    assert "https://elsewhere.example/jobs/acme" in CareersPages(web).links(site)


def test_a_site_that_cannot_be_read_has_no_links(source_pages: Pages, web: WebClient) -> None:
    assert CareersPages(web).links(source_pages({})) == []
