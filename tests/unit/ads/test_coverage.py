from hunter.domain.ads.coverage import AdState, ad_state, coverage, fuller
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import Posting, SourceRef

BERLIN = Location(country="DE", city="Berlin")


def posting(source: str, description: str = "") -> Posting:
    return Posting(
        title="Backend Engineer",
        company="N26",
        location=BERLIN,
        source=SourceRef(source=source, native_id="1"),
        description=description,
    )


def test_an_employer_feed_s_text_is_the_whole_ad() -> None:
    assert ad_state(posting("greenhouse", "We build a bank.")) == AdState.WHOLE


def test_a_search_that_shows_a_few_lines_gives_a_snippet() -> None:
    for source in ("adzuna", "careerjet", "indeed-alert", "jooble", "usajobs"):
        assert ad_state(posting(source, "We build a bank...")) == AdState.SNIPPET


def test_no_text_is_no_ad_wherever_it_came_from() -> None:
    assert ad_state(posting("bundesagentur")) == AdState.NONE
    assert ad_state(posting("adzuna", "  ")) == AdState.NONE


def test_coverage_counts_each_source_s_jobs_by_state() -> None:
    jobs = [
        posting("greenhouse", "text"),
        posting("greenhouse", "text"),
        posting("adzuna", "a few lines"),
        posting("stepstone-alert"),
    ]
    assert coverage(jobs) == {
        "greenhouse": {AdState.WHOLE: 2},
        "adzuna": {AdState.SNIPPET: 1},
        "stepstone-alert": {AdState.NONE: 1},
    }


def test_a_posting_is_fuller_when_it_has_more_of_the_ad() -> None:
    whole, snippet, bare = posting("greenhouse", "ad"), posting("adzuna", "ad"), posting("lever")
    assert fuller(whole, snippet)
    assert fuller(snippet, bare)
    assert not fuller(snippet, whole)
    assert not fuller(whole, posting("eures", "another ad"))
