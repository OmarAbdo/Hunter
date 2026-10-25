from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from hunter.application.discover import Stores, discover, discover_each
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.campaign import Campaign, Rejection
from hunter.domain.discovery.company import Company
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.pooled import Pooled
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
BERLIN = Campaign(id="berlin", title="Berlin", home="DE", countries=frozenset({"DE"}))
DUBAI = Campaign(id="dubai", title="Dubai", home="AE", countries=frozenset({"AE"}))
JOB = Posting(
    title="Backend Engineer",
    company="Nextcloud GmbH",
    location=Location(country="DE", city="Berlin", workplace=Workplace.HYBRID),
    source=SourceRef(source="greenhouse", native_id="1"),
    employer=EmployerRef(ats="greenhouse", board="nextcloud", job_id="1"),
    url="https://job-boards.greenhouse.io/nextcloud/jobs/1",
)


@dataclass
class Feed:
    name: str
    postings: list[Posting] = field(default_factory=list)
    down: bool = False

    def fetch(self) -> Iterable[Posting]:
        if self.down:
            raise SourceUnavailableError(f"{self.name}: HTTP 503")
        return self.postings


class Jobs:
    def __init__(self) -> None:
        self.keys: dict[str, int] = {}

    def add(self, posting: Posting, seen_at: datetime) -> Pooled:
        key = posting.exact_key or posting.fuzzy_key
        known = key in self.keys
        self.keys.setdefault(key, len(self.keys) + 1)
        return Pooled(job_id=self.keys[key], is_new=not known)


class Companies:
    def __init__(self) -> None:
        self.saved: dict[str, Company] = {}

    def get(self, key: str) -> Company | None:
        return self.saved.get(key)

    def save(self, company: Company) -> None:
        self.saved[company.key] = company

    def owner_of(self, board: Board) -> Company | None:
        return next((company for company in self.saved.values() if board in company.feeds), None)


class Verdicts:
    def __init__(self) -> None:
        self.verdicts: dict[tuple[int, str], Rejection | None] = {}

    def decided(self, job_id: int, campaign_id: str) -> bool:
        return (job_id, campaign_id) in self.verdicts

    def record(
        self, job_id: int, campaign_id: str, rejection: Rejection | None, decided_at: datetime
    ) -> None:
        self.verdicts[job_id, campaign_id] = rejection


def stores() -> Stores:
    return Stores(jobs=Jobs(), companies=Companies(), matches=Verdicts())


def test_a_source_that_is_unavailable_is_not_gone_unless_it_says_so() -> None:
    assert not SourceUnavailableError("HTTP 503").gone
    assert SourceUnavailableError("HTTP 404", gone=True).gone


def test_reports_arrive_one_source_at_a_time() -> None:
    later = Feed("ashby:nextcloud", down=True)
    reports = discover_each([Feed("greenhouse:nextcloud", [JOB]), later], [BERLIN], stores(), NOW)
    assert next(reports).source == "greenhouse:nextcloud"
    assert next(reports).error == "ashby:nextcloud: HTTP 503"


def test_each_source_reports_what_it_brought() -> None:
    other = replace(JOB, title="Data Engineer", employer=None, source=SourceRef("greenhouse", "2"))
    [report] = discover([Feed("greenhouse:nextcloud", [JOB, other])], [BERLIN], stores(), NOW)
    assert (report.source, report.fetched, report.new_jobs) == ("greenhouse:nextcloud", 2, 2)
    assert report.taken == {"berlin": 2}
    assert report.error is None


def test_every_campaign_judges_every_new_job() -> None:
    kept = stores()
    discover([Feed("greenhouse:nextcloud", [JOB])], [BERLIN, DUBAI], kept, NOW)
    assert isinstance(kept.matches, Verdicts)
    assert kept.matches.verdicts == {(1, "berlin"): None, (1, "dubai"): Rejection.PLACE}


def test_a_job_seen_again_is_not_judged_again() -> None:
    kept = stores()
    discover([Feed("greenhouse:nextcloud", [JOB])], [BERLIN], kept, NOW)
    [again] = discover([Feed("greenhouse:nextcloud", [JOB])], [BERLIN], kept, NOW)
    assert (again.fetched, again.new_jobs, again.taken) == (1, 0, {})


def test_a_new_campaign_judges_jobs_already_in_the_pool() -> None:
    kept = stores()
    discover([Feed("greenhouse:nextcloud", [JOB])], [DUBAI], kept, NOW)
    [report] = discover([Feed("greenhouse:nextcloud", [JOB])], [BERLIN, DUBAI], kept, NOW)
    assert report.taken == {"berlin": 1}


def test_a_source_that_is_down_is_reported_and_the_others_still_run() -> None:
    down, up = Feed("ashby:nextcloud", down=True), Feed("greenhouse:nextcloud", [JOB])
    first, second = discover([down, up], [BERLIN], stores(), NOW)
    assert (first.fetched, first.new_jobs, first.taken) == (0, 0, {})
    assert first.error == "ashby:nextcloud: HTTP 503"
    assert (second.new_jobs, second.error) == (1, None)


def test_only_jobs_new_to_the_pool_count_as_new() -> None:
    kept = stores()
    discover([Feed("greenhouse:nextcloud", [JOB])], [BERLIN], kept, NOW)
    other = replace(JOB, title="Data Engineer", employer=None, source=SourceRef("greenhouse", "2"))
    [report] = discover([Feed("greenhouse:nextcloud", [JOB, other])], [BERLIN], kept, NOW)
    assert (report.fetched, report.new_jobs) == (2, 1)


def test_the_company_registry_learns_boards_from_postings_and_links() -> None:
    linked = replace(JOB, apply_url="https://jobs.ashbyhq.com/nextcloud/1")
    kept = stores()
    discover([Feed("greenhouse:nextcloud", [linked])], [BERLIN], kept, NOW)
    company = kept.companies.get("nextcloud")
    assert company is not None
    assert company.boards == (
        Board(ats="greenhouse", slug="nextcloud"),
        Board(ats="ashby", slug="nextcloud"),
    )


def test_a_company_without_boards_is_still_registered() -> None:
    alert = replace(JOB, employer=None, url=None, source=SourceRef("indeed-alert", "jk1"))
    kept = stores()
    discover([Feed("indeed-alert", [alert])], [BERLIN], kept, NOW)
    assert kept.companies.get("nextcloud") == Company(name="Nextcloud GmbH")


def test_a_company_keeps_the_website_a_source_names() -> None:
    named = replace(JOB, company_website="https://nextcloud.com")
    kept = stores()
    discover([Feed("eures:x", [named])], [BERLIN], kept, NOW)
    company = kept.companies.get("nextcloud")
    assert company is not None
    assert company.website == "https://nextcloud.com"
