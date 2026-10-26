import time

from hunter.adapters.cli.project import Project
from hunter.adapters.gui.runner import LiveRun
from hunter.adapters.storage.run_log import RunLog


def finished(live: LiveRun) -> dict[str, object]:
    for _ in range(200):
        state = live.state()
        if not state["running"]:
            return state
        time.sleep(0.05)
    raise AssertionError("the run didn't finish")


def test_a_run_started_from_the_window_shows_its_lines_as_they_come(
    quiet_project: Project,
) -> None:
    live = LiveRun(quiet_project)
    assert live.start()
    state = finished(live)
    lines = state["lines"]
    assert isinstance(lines, list)
    assert lines[0].startswith("Reading ")
    assert any(line.startswith("  bundesagentur:") for line in lines)
    assert any(line.startswith("de-swe-berlin turned down") for line in lines)
    [run] = RunLog(quiet_project.database()).latest(1)
    assert run.ended_at is not None


def test_only_one_run_at_a_time(quiet_project: Project) -> None:
    live = LiveRun(quiet_project)
    assert live.start()
    assert not live.start()
    finished(live)
    assert live.start()  # and another once it's over
    finished(live)


def test_before_any_run_nothing_is_running(quiet_project: Project) -> None:
    assert LiveRun(quiet_project).state() == {"running": False, "lines": []}
