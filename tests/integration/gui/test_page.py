import re
from pathlib import Path

from hunter.adapters.gui.server import STATIC

PAGE = (STATIC / "index.html").read_text(encoding="utf-8")
SCRIPT = (STATIC / "app.js").read_text(encoding="utf-8")


def test_every_element_the_script_finds_is_on_the_page() -> None:
    wanted = set(re.findall(r"""byId\(["']([\w-]+)["']\)""", SCRIPT))
    present = set(re.findall(r"""id=["']([\w-]+)["']""", PAGE))
    assert wanted, "the script finds its elements by id"
    assert wanted <= present


def test_text_from_job_sites_is_never_written_as_html() -> None:
    """Titles and company names come from the internet; they're set as text, never as markup."""
    assert not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write", SCRIPT)


def test_only_web_links_are_followed() -> None:
    """A job's link is shown only when it's http or https, never `javascript:`."""
    assert "isWebLink" in SCRIPT
    assert re.search(r"""\^https\?:""", SCRIPT)


def test_the_page_reads_every_view_the_server_has() -> None:
    views = ("/api/campaigns", "/api/jobs", "/api/companies", "/api/pool", "/api/runs/live")
    for view in (*views, "/api/runs"):
        assert view in SCRIPT


def test_the_page_has_light_and_dark_colours() -> None:
    style = (STATIC / "style.css").read_text(encoding="utf-8")
    assert "prefers-color-scheme: dark" in style


def test_nothing_else_lives_next_to_the_page() -> None:
    assert {path.name for path in Path(STATIC).iterdir()} == {"index.html", "app.js", "style.css"}


def test_the_page_keeps_saying_it_is_open() -> None:
    """Hunter stops once its window has been closed for a while; the page says it's open."""
    assert re.search(r'const sayOpen = \(\) => fetch\("/api/alive"\)', SCRIPT)
    assert "setInterval(sayOpen, 5000)" in SCRIPT
