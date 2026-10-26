from pathlib import Path

from hunter.adapters.gui.window import open_window


def test_the_page_opens_in_an_edge_app_window_when_edge_is_there(tmp_path: Path) -> None:
    """An app window: no tabs, no address bar, a window of its own in the task bar."""
    edge = tmp_path / "msedge.exe"
    edge.write_text("")
    started: list[list[str]] = []
    open_window("http://127.0.0.1:8123/", [edge], started.append, lambda _: True)
    assert started == [[str(edge), "--app=http://127.0.0.1:8123/"]]


def test_without_edge_the_page_opens_in_the_usual_browser(tmp_path: Path) -> None:
    browsed: list[str] = []
    open_window("http://127.0.0.1:8123/", [tmp_path / "none.exe"], lambda _: None, browsed.append)
    assert browsed == ["http://127.0.0.1:8123/"]
