from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime

from hunter.application.ports import SourceUnavailableError
from hunter.application.read_ads import read_ads
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import Posting, SourceRef

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


def posting(source: str, native_id: str) -> Posting:
    return Posting(
        title="Softwareentwickler (m/w/d)",
        company="PerZukunft",
        location=Location(country="DE", city="Berlin"),
        source=SourceRef(source=source, native_id=native_id),
    )


class Store:
    def __init__(self, *jobs: Posting) -> None:
        self.jobs = dict(enumerate(jobs, start=1))
        self.kept: dict[int, Posting] = {}
        self.gone: dict[int, datetime] = {}
        self.read_at: dict[int, datetime] = {}

    def wanting(self) -> list[tuple[int, Posting]]:
        return list(self.jobs.items())

    def keep_ad(self, job_id: int, posting: Posting, read_at: datetime) -> None:
        self.kept[job_id] = posting
        self.read_at[job_id] = read_at

    def mark_gone(self, job_id: int, gone_at: datetime) -> None:
        self.gone[job_id] = gone_at


class Reader:
    """Answers with the ad named for each job id; `gone` and `down` ids raise instead."""

    def __init__(self, ads: dict[str, str]) -> None:
        self.ads = ads
        self.asked: list[str] = []

    def read(self, job: Posting) -> str:
        self.asked.append(job.source.native_id)
        if job.source.native_id == "gone":
            raise SourceUnavailableError("HTTP 404", gone=True)
        if job.source.native_id == "down":
            raise SourceUnavailableError("HTTP 503")
        return self.ads[job.source.native_id]


def test_a_job_s_ad_is_read_from_its_source_and_kept() -> None:
    job = posting("bundesagentur", "1")
    store = Store(job)
    counts = read_ads(store, {"bundesagentur": Reader({"1": "Wir suchen Dich."})}, NOW)
    assert store.kept == {1: replace(job, description="Wir suchen Dich.")}
    assert store.read_at == {1: NOW}
    assert counts == {"bundesagentur": Counter(read=1)}


def test_a_job_its_source_no_longer_has_is_marked_gone() -> None:
    store = Store(posting("bundesagentur", "gone"))
    counts = read_ads(store, {"bundesagentur": Reader({})}, NOW)
    assert (store.gone, store.kept) == ({1: NOW}, {})
    assert counts == {"bundesagentur": Counter(gone=1)}


def test_a_job_that_could_not_be_read_is_left_for_the_next_run() -> None:
    store = Store(posting("bundesagentur", "down"), posting("bundesagentur", "empty"))
    counts = read_ads(store, {"bundesagentur": Reader({"empty": "  "})}, NOW)
    assert (store.gone, store.kept) == ({}, {})
    assert counts == {"bundesagentur": Counter(failed=2)}


def test_jobs_from_sources_without_a_reader_are_left_alone() -> None:
    reader = Reader({"1": "Wir suchen Dich."})
    store = Store(posting("linkedin-alert", "9"), posting("bundesagentur", "1"))
    counts = read_ads(store, {"bundesagentur": reader}, NOW)
    assert reader.asked == ["1"]
    assert list(store.kept) == [2]
    assert counts == {"bundesagentur": Counter(read=1)}
