import io
from datetime import UTC, datetime
from pathlib import Path

from hunter.adapters.cli.main import main
from hunter.adapters.cli.probe_command import result_line
from hunter.adapters.cli.probe_targets import companies_to_probe
from hunter.adapters.cli.project import Project
from hunter.adapters.sources.feed_table import APIS
from hunter.adapters.storage.matches import Matches
from hunter.adapters.storage.pool import Pool
from hunter.adapters.storage.probe_log import ProbeLog
from hunter.adapters.storage.registry import Registry
from hunter.application.probe import ProbeResult
from hunter.domain.discovery.boards import Board
from hunter.domain.discovery.company import Company
from hunter.domain.discovery.location import Location
from hunter.domain.discovery.posting import Posting, SourceRef

NOW = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)


def taken(project: Project, company: str, times: int = 1) -> None:
    """`times` jobs of the company, seen in an Indeed alert and taken by the pilot campaign."""
    database = project.database()
    Registry(database).save(Company(name=company))
    for number in range(times):
        posting = Posting(
            title=f"Backend Engineer {number}",
            company=company,
            location=Location(country="DE", city="Berlin"),
            source=SourceRef(source="indeed-alert", native_id=f"{company}-{number}"),
        )
        Matches(database).record(
            Pool(database).add(posting, NOW).job_id, "de-swe-berlin", None, NOW
        )


def probe(project: Path, greenhouse: str, *arguments: str) -> tuple[int, str]:
    """Every system answers from the local server: N26's Greenhouse board, 404 for the rest."""
    out = io.StringIO()
    apis = dict.fromkeys(APIS, greenhouse)
    status = main(["boards", "probe", *arguments], project, apis=apis, out=out)
    return status, out.getvalue()


def test_a_company_whose_jobs_were_taken_gets_its_board(project: Path, greenhouse: str) -> None:
    taken(Project(project), "N26")
    status, out = probe(project, greenhouse)
    company = Registry(Project(project).database()).get("n26")
    assert status == 0
    assert company is not None
    assert company.boards == (Board(ats="greenhouse", slug="n26"),)
    assert "  N26: greenhouse:n26" in out
    assert out.splitlines()[-1] == "1 of 1 found a board"


def test_a_company_without_a_board_is_probed_once(project: Path, greenhouse: str) -> None:
    taken(Project(project), "Zalando")
    _, out = probe(project, greenhouse)
    assert "  Zalando: no board" in out
    assert ProbeLog(Project(project).database()).probed() == {"zalando"}
    _, again = probe(project, greenhouse)
    assert again.splitlines()[0] == "Probing 0 companies for their boards"


def test_the_companies_with_the_most_taken_jobs_come_first(project: Path) -> None:
    taken(Project(project), "Zalando")
    taken(Project(project), "N26", times=2)
    database = Project(project).database()
    assert [company.name for company in companies_to_probe(Project(project), database, 5)] == [
        "N26",
        "Zalando",
    ]
    assert len(companies_to_probe(Project(project), database, 1)) == 1


def test_companies_with_a_board_are_not_probed(project: Path) -> None:
    taken(Project(project), "N26")
    database = Project(project).database()
    registry = Registry(database)
    registry.save(Company(name="N26").with_board(Board(ats="ashby", slug="n26")))
    assert companies_to_probe(Project(project), database, 5) == []


def test_each_result_is_one_line() -> None:
    board = Board(ats="greenhouse", slug="n26")
    assert result_line(ProbeResult(company="N26", board=board)) == "  N26: greenhouse:n26"
    assert result_line(ProbeResult(company="N26", board=None)) == "  N26: no board"
    could_not = ProbeResult(company="N26", board=None, error="greenhouse:n26: no answer")
    assert result_line(could_not) == "  N26: couldn't tell (greenhouse:n26: no answer)"


def test_a_company_that_gains_a_website_is_probed_again(project: Path) -> None:
    taken(Project(project), "N26")
    database = Project(project).database()
    ProbeLog(database).record("n26", NOW)
    assert companies_to_probe(Project(project), database, 5) == []
    Registry(database).save(Company(name="N26").with_website("https://n26.com"))
    assert [company.name for company in companies_to_probe(Project(project), database, 5)] == [
        "N26"
    ]
