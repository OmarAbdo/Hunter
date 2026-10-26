import pytest

from hunter.domain.discovery.language import language_of

GERMAN = (
    "Wir suchen eine erfahrene Entwicklerin oder einen erfahrenen Entwickler für unser Team in "
    "Berlin. Du arbeitest mit uns an der Plattform und bist für die Qualität der Software "
    "verantwortlich, die wir jeden Tag mit unseren Kunden weiterentwickeln."
)
ENGLISH = (
    "We are looking for an experienced engineer to join our team in Berlin. You will work with "
    "us on the platform and you are responsible for the quality of the software that we build "
    "with our customers every day."
)


@pytest.mark.parametrize(("text", "language"), [(GERMAN, "de"), (ENGLISH, "en")])
def test_a_job_ad_s_language_is_told_by_its_common_words(text: str, language: str) -> None:
    assert language_of(text) == language


def test_too_few_words_tell_no_language() -> None:
    """A title alone ("Senior Backend Engineer (m/w/d)") says too little."""
    assert language_of("Senior Backend Engineer (m/w/d)") is None
    assert language_of("") is None


def test_the_language_most_of_the_ad_is_in_wins() -> None:
    """German ads often name a few things in English, and the other way round."""
    assert language_of(GERMAN + " We are hiring.") == "de"


def test_an_ad_evenly_in_two_languages_tells_none() -> None:
    assert language_of(GERMAN + " " + ENGLISH) is None
