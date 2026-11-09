from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from hunter.adapters.sources.feeds.workday import WorkdayAds, WorkdayFeed, posted_at
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

BOARD = "nvidia/wd5/NVIDIAExternalCareerSite"
JOBS = "/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs"
SourceApi = Callable[[str, str | None], str]
NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def postings(source_api: SourceApi, web: WebClient) -> list[Posting]:
    api = source_api(JOBS, "workday-nvidia.json")
    return WorkdayFeed(web, BOARD, "NVIDIA", api=api).fetch()


def test_every_posting_in_the_search_is_read(source_api: SourceApi, web: WebClient) -> None:
    israel, santa_clara = postings(source_api, web)
    assert santa_clara.title.startswith("Senior Software Development Tech Lead")
    assert santa_clara.company == "NVIDIA"
    assert santa_clara.employer == EmployerRef(ats="workday", board=BOARD, job_id="JR2019101")
    assert santa_clara.url is not None
    assert santa_clara.url.startswith(
        "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US-CA-Santa-Clara/"
    )
    assert israel.employer is not None
    assert israel.employer.job_id == "JR2028303"


def test_places_come_from_the_location_text_or_the_job_link(
    source_api: SourceApi, web: WebClient
) -> None:
    israel, santa_clara = postings(source_api, web)
    assert (santa_clara.location.country, santa_clara.location.city) == ("US", "Santa Clara")
    assert israel.location.country == "IL"


@pytest.mark.parametrize(
    ("text", "days"),
    [
        ("Posted Today", 0),
        ("Posted Yesterday", 1),
        ("Posted 3 Days Ago", 3),
        ("Posted 30+ Days Ago", 30),
    ],
)
def test_the_posting_age_gives_its_date(text: str, days: int) -> None:
    assert posted_at(text, NOW) == NOW - timedelta(days=days)


def test_an_unknown_age_gives_no_date() -> None:
    assert posted_at("Posted sometime", NOW) is None


def test_a_board_that_is_gone_makes_the_source_unavailable(
    source_api: SourceApi, web: WebClient
) -> None:
    with pytest.raises(SourceUnavailableError, match="HTTP 404"):
        WorkdayFeed(web, BOARD, "NVIDIA", api=source_api(JOBS, None)).fetch()


def test_the_feed_is_named_after_its_board(web: WebClient) -> None:
    assert WorkdayFeed(web, BOARD, "NVIDIA").name == f"workday:{BOARD}"


def test_a_job_entry_without_a_title_is_skipped(source_api: SourceApi, web: WebClient) -> None:
    """A board answered with one; it ended the whole discovery run (2026-11-09)."""
    api = source_api(JOBS, "workday-untitled.json")
    found = WorkdayFeed(web, BOARD, "NVIDIA", api=api).fetch()
    assert [posting.title for posting in found] == ["RTL Design Engineer, DFT"]


ZALANDO = "zalando/wd3/ZalandoSiteWD"
ZALANDO_JOB = "/job/Berlin/AI-Motion-Expert--all-genders-_2725793-1"
DETAILS = f"/wday/cxs/zalando/ZalandoSiteWD{ZALANDO_JOB}"


def zalando_job() -> Posting:
    return Posting(
        title="AI Motion Expert (all genders)",
        company="Zalando",
        location=Location(country="DE", city="Berlin"),
        source=SourceRef(source="workday", native_id="JR0000001"),
        employer=EmployerRef(ats="workday", board=ZALANDO, job_id="JR0000001"),
        url=f"https://zalando.wd3.myworkdayjobs.com/ZalandoSiteWD{ZALANDO_JOB}",
    )


def test_a_job_s_whole_ad_is_read_from_its_details(source_api: SourceApi, web: WebClient) -> None:
    api = source_api(DETAILS, "workday-job-zalando.json")
    ad = WorkdayAds(web, api=api).read(zalando_job())
    assert ad.startswith("THE ROLE & THE TEAM")
    assert len(ad) > 3000


def test_a_job_the_board_took_down_is_gone(source_api: SourceApi, web: WebClient) -> None:
    with pytest.raises(SourceUnavailableError) as raised:
        WorkdayAds(web, api=source_api(DETAILS, None)).read(zalando_job())
    assert raised.value.gone
