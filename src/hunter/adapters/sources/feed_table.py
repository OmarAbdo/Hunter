"""Every company feed Hunter can read, by applicant tracking system, and each one's web address.
A board in the registry is read with the feed of its system. Sites that refuse Hunter's usual pace
get their own."""

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
from hunter.adapters.sources.feeds import teamtailor, workday
from hunter.application.ports import JobSource
from hunter.domain.pacing import PaceRule

FEEDS: dict[str, Callable[..., JobSource]] = {
    "greenhouse": greenhouse.GreenhouseFeed,
    "ashby": ashby.AshbyFeed,
    "lever": lever.LeverFeed,
    "workable": workable.WorkableFeed,
    "recruitee": recruitee.RecruiteeFeed,
    "personio": personio.PersonioFeed,
    "smartrecruiters": smartrecruiters.SmartRecruitersFeed,
    "teamtailor": teamtailor.TeamtailorFeed,
    "workday": workday.WorkdayFeed,
}
APIS: dict[str, str | tuple[str, ...]] = {
    "greenhouse": greenhouse.API,
    "ashby": ashby.API,
    "lever": lever.HOSTS,
    "workable": workable.API,
    "recruitee": recruitee.API,
    "personio": personio.API,
    "smartrecruiters": smartrecruiters.API,
    "teamtailor": teamtailor.API,
    "workday": workday.API,
}
PACES: dict[str, PaceRule] = {workable.HOST: workable.PACE}
