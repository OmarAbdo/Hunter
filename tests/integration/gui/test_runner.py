import time
from typing import TextIO

from hunter.adapters.cli.parallel_reading import RunControl, RunStoppedError
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
    live = LiveRun(quiet_project)
    assert live.state() == {"running": False, "paused": False, "stopping": False, "lines": []}
    assert not live.pause() and not live.resume() and not live.stop()


def three_sources(project: Project, ids: object, out: TextIO, control: RunControl) -> int:
    """A run of three sources, each read once the run may go on."""
    try:
        for number in range(3):
            [source] = control.gated([Slow(f"source {number}")])
            source.fetch()
            out.write(f"read source {number}\n")
    except RunStoppedError:
        out.write("Stopped.\n")
    return 0


class Slow:
    def __init__(self, name: str) -> None:
        self.name = name

    def fetch(self) -> list[object]:
        time.sleep(0.2)
        return []


def test_a_run_can_be_paused_resumed_and_stopped(quiet_project: Project) -> None:
    live = LiveRun(quiet_project, discover=three_sources)
    assert live.start()
    assert live.pause()
    time.sleep(0.5)
    paused = live.state()
    assert (paused["running"], paused["paused"]) == (True, True)
    assert live.resume()
    assert live.stop()
    assert live.state()["stopping"] is True
    state = finished(live)
    assert state["lines"][-1] == "Stopped."
    assert len(state["lines"]) < 4
    assert (state["paused"], state["stopping"]) == (False, False)


def test_a_run_counts_as_reading_unless_it_is_paused(quiet_project: Project) -> None:
    live = LiveRun(quiet_project, discover=three_sources)
    assert not live.reading()
    live.start()
    assert live.reading()
    live.pause()
    assert not live.reading()
    live.stop()
    finished(live)
