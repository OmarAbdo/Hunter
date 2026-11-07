from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from hunter.adapters.cli.project import Project
from hunter.adapters.storage.matches import Matches
from hunter.adapters.storage.pool import Ads, Pool
from hunter.domain.discovery.campaign import Rejection
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import Posting, SourceRef

Run = Callable[..., tuple[int, str]]
SEEN = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


def posting(source: str, title: str, description: str = "") -> Posting:
    return Posting(
        title=title,
        company="N26",
        location=Location(country="DE", city="Berlin"),
        source=SourceRef(source=source, native_id=title),
        description=description,
    )


def take(project: Path, job: Posting, rejection: Rejection | None = None) -> int:
    database = Project(project).database()
    job_id = Pool(database).add(job, SEEN).job_id
    Matches(database).record(job_id, "berlin", rejection, SEEN)
    return job_id


def test_ads_shows_how_many_taken_jobs_have_their_whole_ad(project: Path, run: Run) -> None:
    take(project, posting("greenhouse", "Backend Engineer", "We build a bank."))
    take(project, posting("greenhouse", "Data Engineer", "We build a bank."))
    take(project, posting("adzuna", "Platform Engineer", "We build..."))
    take(project, posting("stepstone-alert", "Java Developer"))
    gone = take(project, posting("stepstone-alert", "Rust Developer"))
    Ads(Project(project).database()).mark_gone(gone, SEEN)
    take(project, posting("stepstone-alert", "Go Developer"), Rejection.PLACE)
    assert run("ads") == (
        0,
        "source           taken  whole  snippet  none  gone  whole % of open\n"
        "greenhouse           2      2        0     0     0              100\n"
        "stepstone-alert      2      0        0     1     1                0\n"
        "adzuna               1      0        1     0     0                0\n"
        "total                5      2        1     1     1               50\n",
    )


def test_ads_with_nothing_taken_says_so(run: Run) -> None:
    assert run("ads") == (0, "No campaign has taken a job yet.\n")
