from pathlib import Path

import pytest

from hunter.adapters.sources.searches.employer_search import EmployerAds, plain_first
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import Posting, SourceRef

SAVED = Path(__file__).resolve().parents[2] / "fixtures" / "sources"
EUROPACE_AD = "https://hypoport.softgarden.io/job/68122636"
JOB = Posting(
    title="Senior Fullstack Developer (remote) (m/w/d)",
    company="Europace",
    location=Location(country="DE", city="Berlin"),
    source=SourceRef(source="linkedin-alert", native_id="1"),
)


class Search:
    """The web search as the reader sees it: each search's answer in turn, the last one again
    after them; each query kept."""

    def __init__(self, *answers: list[str], down: bool = False) -> None:
        self.answers, self.down = answers, down
        self.queries: list[str] = []

    def links(self, query: str) -> list[str]:
        self.queries.append(query)
        if self.down:
            raise SourceUnavailableError("web search: every engine is resting or at its share")
        return self.answers[min(len(self.queries), len(self.answers)) - 1]


class Pages:
    """Edge as the reader sees it: saved pages by address; every address asked is kept."""

    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.asked: list[str] = []

    def dom(self, url: str) -> str:
        self.asked.append(url)
        if url not in self.pages:
            raise SourceUnavailableError(f"{url}: no page")
        return (SAVED / self.pages[url]).read_text(encoding="utf-8")


def reader(search: Search, pages: Pages, lately: int = 0) -> EmployerAds:
    """`lately`: how many searches for the job got an answer this week."""
    return EmployerAds(search, pages.dom, lambda _: lately)


def test_the_employer_s_own_ad_is_found_by_its_title_and_company() -> None:
    linkedin = "https://de.linkedin.com/jobs/view/senior-fullstack-developer-123"
    other = "https://example.com/careers/backend"
    pages = Pages(
        {other: "personio-job-chrono24.html", EUROPACE_AD: "softgarden-job-hypoport.html"}
    )
    ad = reader(Search([linkedin, other, EUROPACE_AD]), pages).read(JOB)
    assert ad.startswith("Wer sind wir?")
    assert pages.asked == [other, EUROPACE_AD]  # never a job board's page


def test_a_job_whose_ad_isn_t_found_is_left_for_later() -> None:
    pages = Pages({"https://example.com/careers": "personio-job-chrono24.html"})
    with pytest.raises(SourceUnavailableError) as raised:
        reader(Search(["https://example.com/careers"]), pages).read(JOB)
    assert not raised.value.gone


def test_only_an_answer_s_first_results_are_read() -> None:
    links = [f"https://example.com/{number}" for number in range(9)] + [EUROPACE_AD]
    pages = Pages({EUROPACE_AD: "softgarden-job-hypoport.html"})
    with pytest.raises(SourceUnavailableError):
        reader(Search(links, []), pages).read(JOB)
    assert len(pages.asked) == 8


def test_a_miss_is_searched_again_at_once_on_the_next_engine() -> None:
    other = "https://example.com/careers"
    search = Search([other], [other, EUROPACE_AD])
    pages = Pages(
        {other: "personio-job-chrono24.html", EUROPACE_AD: "softgarden-job-hypoport.html"}
    )
    assert reader(search, pages).read(JOB).startswith("Wer sind wir?")
    assert len(search.queries) == 2
    assert pages.asked == [other, EUROPACE_AD]  # a page read for one answer isn't read again


def test_a_job_gets_three_answered_searches_a_week_at_most() -> None:
    other = "https://example.com/careers"
    once = Search([other])
    with pytest.raises(SourceUnavailableError):
        reader(once, Pages({}), lately=1).read(JOB)
    assert len(once.queries) == 2
    thrice = Search([other])
    with pytest.raises(SourceUnavailableError):
        reader(thrice, Pages({}), lately=3).read(JOB)
    assert thrice.queries == []


def test_job_aggregators_copies_are_passed_over() -> None:
    aggregators = [
        "https://bebee.com/de/jobs/senior-fullstack-developer-europace",
        "https://www.jobleads.com/de/job/senior-fullstack-developer",
        "https://fuchsjobs.de/de-de/company/europace",
        "https://www.arbeitnow.com/jobs/companies/europace/fullstack",
        "https://jobs.heise.de/softwareentwicklung/jobs/fullstack",
    ]
    pages = Pages({EUROPACE_AD: "softgarden-job-hypoport.html"})
    assert reader(Search([*aggregators, EUROPACE_AD]), pages).read(JOB).startswith("Wer sind wir?")
    assert pages.asked == [EUROPACE_AD]


def test_a_page_is_read_over_plain_http_and_through_a_browser_only_when_refused() -> None:
    asked: list[str] = []

    def plain(url: str) -> str:
        asked.append(f"plain {url}")
        if "refusing" in url:
            raise SourceUnavailableError(f"{url}: HTTP 403")
        if "gone" in url:
            raise SourceUnavailableError(f"{url}: HTTP 404", gone=True)
        return "plain page"

    def browser(url: str) -> str:
        asked.append(f"browser {url}")
        return "browser page"

    page = plain_first(plain, browser)
    assert page("https://open.example") == "plain page"
    assert page("https://refusing.example") == "browser page"
    with pytest.raises(SourceUnavailableError):
        page("https://gone.example")
    assert asked == [
        "plain https://open.example",
        "plain https://refusing.example",
        "browser https://refusing.example",
        "plain https://gone.example",
    ]


def test_a_search_that_can_t_be_made_leaves_the_job_for_later() -> None:
    with pytest.raises(SourceUnavailableError) as raised:
        reader(Search(down=True), Pages({})).read(JOB)
    assert not raised.value.gone
