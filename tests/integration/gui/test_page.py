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
    views = ("/api/campaigns", "/api/jobs", "/api/companies", "/api/pool", "/api/held")
    for view in (*views, "/api/searches", "/api/runs/live", "/api/runs", "/api/ads"):
        assert view in SCRIPT


def test_the_counts_say_what_they_count() -> None:
    """The pool holds every job found; a campaign takes some of them and turns the rest down."""
    assert "jobs found in all" in SCRIPT
    assert "of the ${judged} jobs in the pool" in SCRIPT
    assert "match the filter" in SCRIPT


def test_the_ads_tab_says_how_many_taken_jobs_have_their_whole_ad() -> None:
    assert '<button id="show-ads" class="tab">Ads</button>' in PAGE
    assert "taken jobs have their whole ad" in SCRIPT


def test_a_run_can_be_paused_resumed_and_stopped_from_the_page() -> None:
    for action in ("pause", "resume", "stop"):
        assert f'runAction("{action}")' in SCRIPT
    assert "`/api/runs/${action}`" in SCRIPT


def test_the_page_has_light_and_dark_colours() -> None:
    style = (STATIC / "style.css").read_text(encoding="utf-8")
    assert "prefers-color-scheme: dark" in style


def test_nothing_else_lives_next_to_the_page() -> None:
    names = {path.name for path in Path(STATIC).iterdir()}
    assert names == {"index.html", "app.js", "style.css", "hunter.svg"}


def test_the_window_shows_hunter_s_icon() -> None:
    assert '<link rel="icon" href="/hunter.svg" type="image/svg+xml">' in PAGE


def test_the_page_keeps_saying_it_is_open() -> None:
    """Hunter stops once its window has been closed for a while; the page says it's open."""
    assert re.search(r'const sayOpen = \(\) => fetch\("/api/alive"\)', SCRIPT)
    assert "setInterval(sayOpen, 5000)" in SCRIPT
