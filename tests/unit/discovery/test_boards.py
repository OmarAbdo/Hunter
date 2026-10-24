import pytest

from hunter.domain.discovery.boards import Board, board_from_link


@pytest.mark.parametrize(
    ("link", "ats", "slug"),
    [
        ("https://job-boards.greenhouse.io/gitlab/jobs/8123", "greenhouse", "gitlab"),
        ("https://boards.eu.greenhouse.io/embed/job_board?for=nebius", "greenhouse", "nebius"),
        ("https://jobs.eu.lever.co/olx/0a1b-2c3d", "lever", "olx"),
        ("https://jobs.ashbyhq.com/getyourguide/123?utm=x", "ashby", "getyourguide"),
        ("https://apply.workable.com/a11/j/ABC123/", "workable", "a11"),
        ("https://idnow.jobs.personio.de/job/1234#apply", "personio", "idnow.de"),
        ("https://jobs.smartrecruiters.com/Visa/7438", "smartrecruiters", "Visa"),
        ("https://mollie.recruitee.com/o/backend-engineer", "recruitee", "mollie"),
        ("https://career.teamtailor.com/jobs/12-engineer", "teamtailor", "career"),
        (
            "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/X",
            "workday",
            "nvidia/wd5/NVIDIAExternalCareerSite",
        ),
        ("https://join.com/companies/momox/12345-engineer", "join", "momox"),
    ],
)
def test_a_link_names_the_board(link: str, ats: str, slug: str) -> None:
    assert board_from_link(link) == Board(ats=ats, slug=slug)


@pytest.mark.parametrize(
    "link",
    [
        "https://de.indeed.com/rc/clk/dl?jk=53e2194f9af64745",
        "https://boards-api.greenhouse.io/v1/boards",
        "https://jobs.lever.co/",
        "",
    ],
)
def test_other_links_name_no_board(link: str) -> None:
    assert board_from_link(link) is None


def test_a_board_key_is_its_system_and_slug() -> None:
    assert Board(ats="ashby", slug="getyourguide").key == "ashby:getyourguide"
