from hunter.domain.ads.employer_ad import fits, names_company, search_query
from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import Posting, SourceRef

JOB = Posting(
    title="Senior Fullstack Developer (remote) (m/w/d)",
    company="Europace",
    location=Location(country="DE", city="Berlin"),
    source=SourceRef(source="linkedin-alert", native_id="1"),
)


def test_an_ad_fits_when_it_names_the_job_s_title_and_company() -> None:
    assert fits(JOB, "Senior Fullstack Developer (remote) (w/m/d)", "EUROPACE AG")


def test_an_ad_for_another_title_or_company_doesn_t_fit() -> None:
    assert not fits(JOB, "Senior Backend Developer (remote) (w/m/d)", "Europace AG")
    assert not fits(JOB, "Senior Fullstack Developer (remote) (w/m/d)", "Hypoport SE")


def test_an_ad_without_a_title_or_company_never_fits() -> None:
    assert not fits(JOB, "", "Europace")
    assert not fits(JOB, "Senior Fullstack Developer (remote)", "")


def test_the_search_asks_for_the_company_by_name_and_the_title_without_its_marker() -> None:
    assert search_query(JOB) == '"Europace" Senior Fullstack Developer (remote)'


def test_a_board_is_the_company_s_when_its_name_holds_a_word_of_the_company_s() -> None:
    assert names_company(Board("successfactors", "careers.nexus-ag.de"), "Nexus")
    assert names_company(Board("workday", "flaschenpost/wd103/flaschenpost"), "flaschenpost SE")
    assert not names_company(Board("smartrecruiters", "Bertelsmann-Jobs"), "Arvato Systems")
    assert not names_company(Board("ashby", "abc"), "ABC")  # words of four letters or more only
    assert not names_company(Board("greenhouse", "nexus"), "")
