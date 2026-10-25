from collections.abc import Callable
from pathlib import Path

from hunter.adapters.storage.database import open_database
from hunter.adapters.storage.pool import Pool
from hunter.adapters.storage.registry import Registry

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
