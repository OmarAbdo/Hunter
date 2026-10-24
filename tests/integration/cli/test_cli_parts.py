import io
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hunter.adapters.cli.boards_command import add_boards
from hunter.adapters.cli.discover_command import chosen
from hunter.adapters.cli.project import Project, stores_of
from hunter.adapters.cli.report import report_text, table
from hunter.adapters.cli.sources import alert_sources_of, feeds_of
from hunter.adapters.matches import Matches
from hunter.application.discover import SourceReport
from hunter.domain.discovery.campaign import Campaign, Rejection

BERLIN = Campaign(id="berlin", title="Berlin", home="DE", countries=frozenset({"DE"}))
DUBAI = Campaign(id="dubai", title="Dubai", home="AE", countries=frozenset({"AE"}))


def test_the_project_keeps_its_database_in_var(tmp_path: Path) -> None:
    Project(tmp_path).database()
    assert (tmp_path / "var" / "hunter.db").is_file()
    assert Project(tmp_path).campaigns_folder == tmp_path / "campaigns"


def test_the_report_shows_each_source_the_totals_and_the_reasons(tmp_path: Path) -> None:
    database = Project(tmp_path).database()
    Matches(database).record(1, "berlin", Rejection.PLACE, datetime.now(UTC))
    reports = [
        SourceReport("greenhouse:n26", fetched=3, new_jobs=3, taken={"berlin": 1}),
        SourceReport("ashby:enpal", error="ashby:enpal: HTTP 503"),
    ]
    assert report_text(reports, [BERLIN], Matches(database)).splitlines() == [
        "source          fetched  new  berlin",
        "greenhouse:n26        3    3       1",
        "ashby:enpal           0    0       0",
        "total                 3    3       1",
        "ashby:enpal: ashby:enpal: HTTP 503",
        "berlin turned down: place 1",
    ]


def test_a_campaign_that_turned_nothing_down_says_so(tmp_path: Path) -> None:
    text = report_text([], [BERLIN], Matches(Project(tmp_path).database()))
    assert text.splitlines() == [
        "source  fetched  new  berlin",
        "total         0    0       0",
        "berlin turned down: nothing",
    ]


def test_tables_align_numbers_right() -> None:
    assert table([["a", "1"], ["bbb", "22"]]) == ["a     1", "bbb  22"]


def test_the_campaigns_named_are_chosen_and_none_named_means_all() -> None:
    assert chosen([BERLIN, DUBAI], ["dubai"]) == [DUBAI]
    assert chosen([BERLIN, DUBAI], []) == [BERLIN, DUBAI]
    with pytest.raises(LookupError, match="no campaign rome"):
        chosen([BERLIN], ["rome"])


def test_every_known_board_in_the_registry_is_a_feed(tmp_path: Path) -> None:
    project = Project(tmp_path)
    links = ["https://jobs.ashbyhq.com/enpal", "https://jobs.lever.co/olx"]
    add_boards(project, links, "Enpal", io.StringIO())
    assert [source.name for source in feeds_of(project, project.database())] == ["ashby:enpal"]
    company = stores_of(project.database()).companies.get("enpal")
    assert company is not None
    assert [board.key for board in company.boards] == ["ashby:enpal", "lever:olx"]
    assert stores_of(project.database()).companies.get("enpal") is not None


def test_without_credentials_there_are_no_alert_sources(tmp_path: Path) -> None:
    project = Project(tmp_path)
    assert alert_sources_of(project, project.database()) == []
