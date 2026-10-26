from collections.abc import Callable
from pathlib import Path

import pytest

from hunter.adapters.cli import discover_command
from hunter.adapters.cli.sources import sources_of
from hunter.adapters.storage.database import open_database
from hunter.adapters.storage.pool import Pool
from hunter.adapters.storage.registry import Registry
from hunter.adapters.storage.run_log import RunLog
from hunter.application.discover import SourceReport

Run = Callable[..., tuple[int, str]]


def test_a_board_link_adds_the_company_to_the_registry(project: Path, run: Run) -> None:
    status, out = run("boards", "add", "https://jobs.ashbyhq.com/enpal", "--company", "Enpal")
    company = Registry(open_database(project / "var" / "hunter.db")).get("enpal")
    assert status == 0
    assert company is not None
    assert [board.key for board in company.boards] == ["ashby:enpal"]
    assert "Enpal: ashby:enpal" in out


def test_a_link_that_names_no_board_is_refused(run: Run) -> None:
    status, out = run("boards", "add", "https://example.com/careers")
    assert status == 1
    assert "names no job board" in out


def test_discover_reads_the_registry_feeds_and_reports_each_source(project: Path, run: Run) -> None:
    run("boards", "add", "https://job-boards.greenhouse.io/n26", "--company", "N26")
    status, out = run("discover")
    assert status == 0
    assert "greenhouse:n26" in out
    assert Pool(open_database(project / "var" / "hunter.db")).job_count() == 3
    assert "de-swe-berlin" in out


def test_a_source_that_is_down_is_reported(run: Run) -> None:
    run("boards", "add", "https://job-boards.greenhouse.io/gone", "--company", "Gone")
    status, out = run("discover")
    assert status == 0
    assert "greenhouse:gone" in out
    assert "HTTP 404" in out


def test_an_unknown_campaign_is_refused(run: Run) -> None:
    status, out = run("discover", "--campaign", "nowhere")
    assert status == 1
    assert "no campaign nowhere" in out


def test_discover_runs_the_searches_the_campaigns_name(run: Run) -> None:
    status, out = run("discover")
    assert status == 0
    assert "bundesagentur:Softwareentwickler@Berlin" in out


def test_a_campaign_with_an_unknown_search_source_is_refused(project: Path, run: Run) -> None:
    pilot = project / "campaigns" / "de-swe-berlin.toml"
    nowhere = pilot.read_text(encoding="utf-8").replace('"bundesagentur"', '"nowhere"')
    pilot.write_text(nowhere, encoding="utf-8")
    status, out = run("discover")
    assert status == 1
    assert "no search source nowhere" in out


def test_discover_says_how_many_job_board_jobs_it_linked(run: Run) -> None:
    _, out = run("discover")
    assert "0 job-board jobs linked to the employer's own posting" in out


def test_a_discover_run_keeps_its_report_in_the_database(project: Path, run: Run) -> None:
    run("boards", "add", "https://job-boards.greenhouse.io/n26", "--company", "N26")
    run("discover")
    log = RunLog(open_database(project / "var" / "hunter.db"))
    [kept] = log.latest(10)
    reports = {report.source: report for report in log.reports(kept.run_id)}
    assert kept.campaign_ids == ("de-swe-berlin",)
    assert kept.ended_at is not None
    assert kept.ended_at >= kept.started_at
    assert kept.linked_jobs == 0
    assert reports["greenhouse:n26"] == SourceReport(
        "greenhouse:n26", fetched=3, new_jobs=3, taken={"de-swe-berlin": 1}
    )
    assert "HTTP 404" in str(reports["bundesagentur:Softwareentwickler@Berlin"].error)


class Interrupted:
    name = "greenhouse:slow"

    def fetch(self) -> list[object]:
        raise KeyboardInterrupt


def test_a_stopped_run_keeps_the_sources_read_until_then(
    project: Path, run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    def then_stopped(*arguments: object) -> list[object]:
        return [*sources_of(*arguments), Interrupted()]

    run("boards", "add", "https://job-boards.greenhouse.io/n26", "--company", "N26")
    monkeypatch.setattr(discover_command, "sources_of", then_stopped)
    status, _ = run("discover")
    log = RunLog(open_database(project / "var" / "hunter.db"))
    [kept] = log.latest(10)
    assert status == 130
    assert kept.ended_at is None
    assert "greenhouse:n26" in [report.source for report in log.reports(kept.run_id)]
