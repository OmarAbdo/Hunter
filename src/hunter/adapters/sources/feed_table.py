"""Every company feed Hunter can read, by applicant tracking system, and each one's web address.
A board in the registry is read with the feed of its system. Sites that refuse Hunter's usual pace
get their own. One entry a line, in alphabetical order, so that sources added at the same time
rarely touch the same line."""

from collections.abc import Callable

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
from hunter.application.ports import JobSource
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
