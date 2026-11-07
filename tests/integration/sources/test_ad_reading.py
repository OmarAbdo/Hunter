from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hunter.adapters.ad_reading import ads_line, read_taken_ads, readers_of
from hunter.adapters.cli.project import Project
from hunter.adapters.storage.matches import Matches
from hunter.adapters.sources.reading import JobPageAds
from hunter.adapters.storage.pool import Ads, Pool
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import Posting, SourceRef

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
DETAILS = "/pc/v4/jobdetails/MTM1MDktMDAwMDIxMTE3NjQwMDEtUw=="


def take(project: Project, reference: str) -> int:
    database = project.database()
    posting = Posting(
        title=f"DevSecOps Engineer {reference}",
        company="BWI GmbH",
        location=Location(country="DE", city="Berlin"),
        source=SourceRef(source="bundesagentur", native_id=reference),
    )
    job_id = Pool(database).add(posting, NOW).job_id
    Matches(database).record(job_id, "berlin", None, NOW)
    return job_id


def test_the_bundesagentur_s_taken_jobs_get_their_ad_or_are_gone(
    tmp_path: Path, source_pages: Callable[[Mapping[str, str]], str]
) -> None:
    api = source_pages({DETAILS: "bundesagentur-jobdetails-bwi.json"})
    project = Project(tmp_path, {"bundesagentur": api})
    found, closed = take(project, "13509-00002111764001-S"), take(project, "10000-1-S")
    assert read_taken_ads(project, NOW) == {"bundesagentur": Counter(read=1, gone=1)}
    assert Pool(project.database()).posting(found).description.startswith("Sorge gemeinsam")
    assert closed not in dict(Ads(project.database()).wanting())


def test_the_line_says_what_each_source_s_ads_came_to() -> None:
    outcomes = {"bundesagentur": Counter(read=230, gone=8, failed=3), "xing-alert": Counter(gone=2)}
    assert ads_line(outcomes) == (
        "Ads: bundesagentur 230 read, 8 gone, 3 failed; xing-alert 2 gone\n"
    )
    assert ads_line({}) == "Ads: nothing to read\n"


def test_the_sources_read_one_job_at_a_time(tmp_path: Path) -> None:
    assert sorted(readers_of(Project(tmp_path))) == [
        "bundesagentur",
        "smartrecruiters",
        "softgarden",
    ]


FULLSTACK = Posting(
    title="Senior Fullstack Developer (remote) (w/m/d)",
    company="EUROPACE AG",
    location=Location(country="DE", city="Berlin"),
    source=SourceRef(source="softgarden", native_id="68122636"),
)


def test_a_job_s_whole_ad_is_read_from_its_page_s_job_data(
    web: WebClient, source_pages: Callable[[Mapping[str, str]], str]
) -> None:
    site = source_pages({"/job/68122636": "softgarden-job-hypoport.html"})
    ad = JobPageAds(web).read(replace(FULLSTACK, url=f"{site}/job/68122636"))
    assert ad.startswith("Wer sind wir?")
    assert ad.endswith("www.hypoport.de | www.europace.de")


def test_a_page_without_job_data_has_no_ad(
    web: WebClient, source_pages: Callable[[Mapping[str, str]], str]
) -> None:
    site = source_pages({"/de/vacancies": "softgarden-hypoport.html"})
    assert JobPageAds(web).read(replace(FULLSTACK, url=f"{site}/de/vacancies")) == ""


def test_a_job_page_that_was_taken_down_is_gone(
    web: WebClient, source_pages: Callable[[Mapping[str, str]], str]
) -> None:
    job = replace(FULLSTACK, url=f"{source_pages({})}/job/68122636")
    with pytest.raises(SourceUnavailableError) as raised:
        JobPageAds(web).read(job)
    assert raised.value.gone
