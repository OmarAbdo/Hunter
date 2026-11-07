from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from hunter.adapters.ad_reading import ads_line, read_taken_ads, readers_of
from hunter.adapters.cli.project import Project
from hunter.adapters.storage.matches import Matches
from hunter.adapters.storage.pool import Ads, Pool
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
    assert sorted(readers_of(Project(tmp_path))) == ["bundesagentur", "smartrecruiters"]
