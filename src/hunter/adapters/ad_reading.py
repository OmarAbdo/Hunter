"""Reading the ads of taken jobs that lack them, at the end of every discovery run: the sources
Hunter can read one job at a time, paced like the rest of the run. Job-alert jobs and Adzuna's are
read through headless Edge, with its own profile in var/."""

from collections import Counter
from datetime import datetime

from hunter.adapters.cli.project import Project
from hunter.adapters.sources.feed_table import ADS, PACE, PARTIAL
from hunter.adapters.sources import reading, smartrecruiters
from hunter.adapters.sources.alerts import alert_ads, linkedin_ads
from hunter.adapters.sources.searches import bundesagentur
from hunter.adapters.storage.holds import kept_pacing
from hunter.adapters.storage.pool import Ads
from hunter.adapters.web_client import WebClient
from hunter.application.ports import AdReader
from hunter.application.read_ads import read_ads

OUTCOMES = ("read", "gone", "failed")


def read_taken_ads(
    project: Project, now: datetime, run_id: int | None = None
) -> dict[str, Counter[str]]:
    """Each source's taken jobs that lacked their ad, counted as read, gone or failed. After a
    run (`run_id`), first the jobs its boards no longer list are gone, counted as "boards"."""
    ads = Ads(project.database())
    dropped = ads.mark_dropped(run_id, PARTIAL, now) if run_id is not None else 0
    outcomes = read_ads(ads, readers_of(project), now)
    return {"boards": Counter(gone=dropped), **outcomes} if dropped else outcomes


def readers_of(project: Project) -> dict[str, AdReader]:
    paces = {linkedin_ads.HOST: linkedin_ads.PACE}
    web = WebClient(kept_pacing(paces, PACE, project.database))
    apis = {"bundesagentur": bundesagentur.API, "smartrecruiters": smartrecruiters.API}
    apis.update({source: api for source, api in project.apis.items() if source in apis})
    return {
        "bundesagentur": bundesagentur.BundesagenturAds(web, api=apis["bundesagentur"]),
        "smartrecruiters": smartrecruiters.SmartRecruitersAds(web, api=apis["smartrecruiters"]),
        **{system: reader(web) for system, reader in ADS.items()},
        **alert_ads.edge_readers(
            project.root / "var" / "edge-ads",
            project.database(),
            lambda url: reading.read_text(web, url, None, reading.BROWSER),
        ),
        "linkedin-alert": linkedin_ads.LinkedInAds(web),
    }


def ads_line(outcomes: dict[str, Counter[str]]) -> str:
    """Each source's outcomes, those that happened, in the order read, gone, failed."""
    parts = (
        f"{source} " + ", ".join(f"{counts[name]} {name}" for name in OUTCOMES if counts[name])
        for source, counts in outcomes.items()
    )
    return f"Ads: {'; '.join(parts) or 'nothing to read'}\n"
