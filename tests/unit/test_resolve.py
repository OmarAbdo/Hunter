from dataclasses import replace

from hunter.application.resolve import resolve
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import EmployerRef, Posting, SourceRef

SEEN = Posting(
    title="Senior Backend Engineer",
    company="N26 GmbH",
    location=Location(country="DE", city="Berlin"),
    source=SourceRef(source="indeed-alert", native_id="abc123"),
)
EMPLOYER = replace(
    SEEN,
    company="N26",
    source=SourceRef(source="greenhouse", native_id="4711"),
    employer=EmployerRef(ats="greenhouse", board="n26", job_id="4711"),
)


class Links:
    """Job-board jobs by id, and the employer jobs on the boards of each company."""

    def __init__(
        self, unresolved: dict[int, Posting], employer: dict[str, list[tuple[int, Posting]]]
    ) -> None:
        self.left = unresolved
        self.employer = employer
        self.asked: list[str] = []
        self.merged: list[tuple[int, int]] = []

    def unresolved(self) -> list[tuple[int, Posting]]:
        return list(self.left.items())

    def employer_jobs(self, company_key: str) -> list[tuple[int, Posting]]:
        self.asked.append(company_key)
        return self.employer.get(company_key, [])

    def merge(self, job_id: int, into: int) -> None:
        self.merged.append((job_id, into))


def test_a_job_board_job_is_merged_into_the_employer_posting() -> None:
    links = Links({7: SEEN}, {"n26": [(1, EMPLOYER)]})
    assert resolve(links) == 1
    assert links.merged == [(7, 1)]


def test_a_job_without_an_employer_posting_stays() -> None:
    links = Links({7: SEEN, 8: replace(SEEN, company="Nowhere")}, {"n26": []})
    assert resolve(links) == 0
    assert links.merged == []


def test_each_company_s_employer_jobs_are_looked_up_once() -> None:
    other = replace(SEEN, title="Data Engineer", source=SourceRef("bundesagentur", "x"))
    links = Links({7: SEEN, 8: other}, {"n26": [(1, EMPLOYER)]})
    resolve(links)
    assert links.asked == ["n26"]
