from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import replace
from functools import partial
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from hunter.adapters.ad_reading import ads_line, read_taken_ads, readers_of
from hunter.adapters.cli.project import Project
from hunter.adapters.storage.matches import Matches
from hunter.adapters.sources.alerts.linkedin_ads import LinkedInAds
from hunter.adapters.sources.reading import JobPageAds, ad_on_page, read_page
from hunter.adapters.storage.pool import Ads, Pool
from hunter.adapters.storage.run_log import RunLog
from hunter.adapters.web_client import WebClient
from hunter.application.discover import SourceReport
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

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
        "adzuna",
        "bundesagentur",
        "careerjet",
        "indeed-alert",
        "linkedin-alert",
        "personio",
        "smartrecruiters",
        "softgarden",
        "stepstone-alert",
        "workday",
        "xing-alert",
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
    ad = JobPageAds(partial(read_page, web)).read(replace(FULLSTACK, url=f"{site}/job/68122636"))
    assert ad.startswith("Wer sind wir?")
    assert ad.endswith("www.hypoport.de | www.europace.de")


def test_a_page_without_job_data_has_no_ad(
    web: WebClient, source_pages: Callable[[Mapping[str, str]], str]
) -> None:
    site = source_pages({"/de/vacancies": "softgarden-hypoport.html"})
    assert (
        JobPageAds(partial(read_page, web)).read(replace(FULLSTACK, url=f"{site}/de/vacancies"))
        == ""
    )


def test_a_job_page_that_was_taken_down_is_gone(
    web: WebClient, source_pages: Callable[[Mapping[str, str]], str]
) -> None:
    job = replace(FULLSTACK, url=f"{source_pages({})}/job/68122636")
    with pytest.raises(SourceUnavailableError) as raised:
        JobPageAds(partial(read_page, web)).read(job)
    assert raised.value.gone


SAVED = Path(__file__).resolve().parents[2] / "fixtures" / "sources"
ADZUNA = Posting(
    title="DevOps Engineer - On Premises Cloud (m/w/d)",
    company="Bundesdruckerei-Gruppe",
    location=Location(country="DE", city="Berlin"),
    source=SourceRef(source="adzuna", native_id="5911828849"),
    url="https://www.adzuna.de/details/5911828849",
)


def edge_page(saved: str) -> Callable[[str], str]:
    """Edge as the reader sees it: the saved page, for the job's own address only."""
    return {ADZUNA.url: (SAVED / saved).read_text(encoding="utf-8")}.__getitem__


def test_an_adzuna_job_s_whole_ad_is_read_from_its_details_page() -> None:
    ad = JobPageAds(edge_page("adzuna-page-live.html")).read(ADZUNA)
    assert ad.startswith("DevOps Engineer - On Premises Cloud (m/w/d)\n\nGestalten Sie")
    assert len(ad) > 3000


def test_an_adzuna_job_that_is_out_of_date_is_gone() -> None:
    with pytest.raises(SourceUnavailableError) as raised:
        JobPageAds(edge_page("adzuna-page-outdated.html")).read(ADZUNA)
    assert raised.value.gone


def test_a_page_that_was_not_found_is_gone() -> None:
    """Adzuna's page for an id it no longer knows: the page, as Edge shows it, has only this."""
    page = "<title>Seite nicht gefunden - adzuna.de</title><h1>Seite nicht gefunden</h1>"
    with pytest.raises(SourceUnavailableError) as raised:
        ad_on_page(page, ADZUNA.url or "")
    assert raised.value.gone


def test_a_personio_job_s_whole_ad_is_read_from_its_page(
    tmp_path: Path, source_pages: Callable[[Mapping[str, str]], str]
) -> None:
    """Some Personio boards publish their feed without the ads; the job's page has it."""
    site = source_pages({"/job/2827202": "personio-job-chrono24.html"})
    job = replace(FULLSTACK, source=SourceRef("personio", "2827202"), url=f"{site}/job/2827202")
    ad = readers_of(Project(tmp_path))["personio"].read(job)
    assert ad.startswith("About\n\nChrono24 is the world's leading marketplace")


def test_after_a_run_the_jobs_its_boards_dropped_are_counted_gone(tmp_path: Path) -> None:
    project = Project(tmp_path)
    database = project.database()
    job = replace(FULLSTACK, source=SourceRef("greenhouse", "7"), description="We build.")
    job = replace(job, employer=EmployerRef("greenhouse", "europace", "7"))
    job_id = Pool(database).add(job, NOW - timedelta(days=1)).job_id
    Matches(database).record(job_id, "berlin", None, NOW)
    log = RunLog(database, clock=lambda: NOW)
    run = log.start(["berlin"])
    log.record(run.run_id, SourceReport("greenhouse:europace", fetched=4))
    assert read_taken_ads(project, NOW, run.run_id) == {"boards": Counter(gone=1)}


def test_linkedin_jobs_are_read_from_linkedin_s_guest_page_not_searched_for(
    tmp_path: Path,
) -> None:
    assert isinstance(readers_of(Project(tmp_path))["linkedin-alert"], LinkedInAds)
