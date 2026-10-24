from collections.abc import Callable

import pytest

from hunter.adapters.cli import discover_command
from hunter.adapters.cli.project import Project

Run = Callable[..., tuple[int, str]]


def test_each_source_is_reported_as_soon_as_it_is_read(run: Run) -> None:
    run("boards", "add", "https://job-boards.greenhouse.io/n26", "--company", "N26")
    run("boards", "add", "https://job-boards.greenhouse.io/gone", "--company", "Gone")
    _, out = run("discover")
    lines = out.splitlines()
    assert lines[0] == "Reading 2 sources for de-swe-berlin"
    assert lines[1].startswith("  greenhouse:gone: failed (127.0.0.1")
    assert "HTTP 404" in lines[1]
    assert lines[2] == "  greenhouse:n26: 3 fetched, 3 new, 1 taken"


class Interrupted:
    name = "greenhouse:slow"

    def fetch(self) -> list[object]:
        raise KeyboardInterrupt


def test_stopping_a_run_says_what_happened_instead_of_a_traceback(
    run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupted(project: Project, database: object) -> list[Interrupted]:
        return [Interrupted()]

    monkeypatch.setattr(discover_command, "sources_of", interrupted)
    status, out = run("discover")
    assert status == 130
    assert out.splitlines()[-1] == "Stopped. Everything read until now is kept."
