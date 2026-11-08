"""Reading the ads of taken jobs that lack them, at the end of every discovery run: the sources
Hunter can read one job at a time, paced like the rest of the run. Job-alert jobs and Adzuna's are
read through headless Edge, with its own profile in var/."""

from collections import Counter
from datetime import datetime

from hunter.adapters.cli.project import Project
from hunter.adapters.sources.feed_table import PACE
from hunter.adapters.sources import personio, reading, smartrecruiters
from hunter.adapters.sources.alerts.alert_ads import edge_readers
from hunter.adapters.sources.searches import bundesagentur
from hunter.adapters.storage.holds import kept_pacing
from hunter.adapters.storage.pool import Ads
from hunter.adapters.web_client import WebClient
from hunter.application.ports import AdReader
from hunter.application.read_ads import read_ads

OUTCOMES = ("read", "gone", "failed")


def read_taken_ads(project: Project, now: datetime) -> dict[str, Counter[str]]:
    """Each source's taken jobs that lacked their ad, counted as read, gone or failed."""
    return read_ads(Ads(project.database()), readers_of(project), now)


def readers_of(project: Project) -> dict[str, AdReader]:
    web = WebClient(kept_pacing({}, PACE, project.database))
    apis = {"bundesagentur": bundesagentur.API, "smartrecruiters": smartrecruiters.API}
    apis.update({source: api for source, api in project.apis.items() if source in apis})
    return {
        "bundesagentur": bundesagentur.BundesagenturAds(web, api=apis["bundesagentur"]),
        "personio": personio.PersonioAds(web),
        "smartrecruiters": smartrecruiters.SmartRecruitersAds(web, api=apis["smartrecruiters"]),
        "softgarden": reading.JobPageAds(lambda url: reading.read_page(web, url)),
        **edge_readers(project.root / "var" / "edge-ads"),
    }


def ads_line(outcomes: dict[str, Counter[str]]) -> str:
    """Each source's outcomes, those that happened, in the order read, gone, failed."""
    parts = (
        f"{source} " + ", ".join(f"{counts[name]} {name}" for name in OUTCOMES if counts[name])
        for source, counts in outcomes.items()
    )
    return f"Ads: {'; '.join(parts) or 'nothing to read'}\n"
