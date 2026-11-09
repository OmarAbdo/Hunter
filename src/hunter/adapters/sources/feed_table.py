"""Every company feed Hunter can read, by applicant tracking system, and each one's web address.
A board in the registry is read with the feed of its system. Sites that refuse Hunter's usual pace
get their own. One entry a line, in alphabetical order, so that sources added at the same time
rarely touch the same line."""

from collections.abc import Callable
from datetime import timedelta

from hunter.adapters.sources import (
    ashby,
    greenhouse,
    lever,
    personio,
    recruitee,
    smartrecruiters,
    workable,
)
from hunter.adapters.sources.feeds import (
    coveto,
    dvinci,
    onlyfy,
    rexx,
    softgarden,
    successfactors,
    teamtailor,
    workday,
)
from hunter.adapters.sources.reading import JobPageAds, read_page
from hunter.adapters.web_client import WebClient
from hunter.application.ports import AdReader, JobSource
from hunter.domain.pacing import PaceRule

FEEDS: dict[str, Callable[..., JobSource]] = {
    "ashby": ashby.AshbyFeed,
    "coveto": coveto.CovetoFeed,
    "dvinci": dvinci.DvinciFeed,
    "greenhouse": greenhouse.GreenhouseFeed,
    "lever": lever.LeverFeed,
    "onlyfy": onlyfy.OnlyfyFeed,
    "personio": personio.PersonioFeed,
    "recruitee": recruitee.RecruiteeFeed,
    "rexx": rexx.RexxFeed,
    "smartrecruiters": smartrecruiters.SmartRecruitersFeed,
    "softgarden": softgarden.SoftgardenFeed,
    "successfactors": successfactors.SuccessFactorsFeed,
    "teamtailor": teamtailor.TeamtailorFeed,
    "workable": workable.WorkableFeed,
    "workday": workday.WorkdayFeed,
}
APIS: dict[str, str | tuple[str, ...]] = {
    "ashby": ashby.API,
    "coveto": coveto.API,
    "dvinci": dvinci.API,
    "greenhouse": greenhouse.API,
    "lever": lever.HOSTS,
    "onlyfy": onlyfy.API,
    "personio": personio.API,
    "recruitee": recruitee.API,
    "rexx": rexx.API,
    "smartrecruiters": smartrecruiters.API,
    "softgarden": softgarden.API,
    "successfactors": successfactors.API,
    "teamtailor": teamtailor.API,
    "workable": workable.API,
    "workday": workday.API,
}
PACES: dict[str, PaceRule] = {workable.HOST: workable.PACE}
# The systems whose list leaves a job's ad out, and the reader that fetches it, job by job.
ADS: dict[str, Callable[[WebClient], AdReader]] = {
    "personio": personio.PersonioAds,
    "softgarden": lambda web: JobPageAds(lambda url: read_page(web, url)),
    "workday": workday.WorkdayAds,
}
# Systems whose list of a board can stop short of all its jobs: at how many jobs the feed stops,
# or 0 where any one job can be missed (rexx reads a page per job). A board read below its cut-off
# lists every job it has, so a job missing from it is gone.
PARTIAL: dict[str, int] = {
    "onlyfy": onlyfy.PAGE_SIZE * onlyfy.MOST_PAGES,
    "rexx": 0,
    "smartrecruiters": smartrecruiters.MOST,
    "workday": workday.PAGE * workday.MOST_PAGES,
}
PACE = PaceRule(min_gap=timedelta(seconds=1))  # every other site's
