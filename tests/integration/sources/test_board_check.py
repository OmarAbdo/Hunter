from collections.abc import Callable
from datetime import timedelta

import pytest

from hunter.adapters.sources.feeds.board_check import FeedCheck
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.boards import Board
from hunter.domain.pacing import Pacing, PaceRule

N26 = Board(ats="greenhouse", slug="n26")
JOBS = "/v1/boards/n26/jobs?content=true"
SourceApi = Callable[[str, str | None], str]


def check(source_api: SourceApi, web: WebClient, saved: str | None) -> FeedCheck:
    return FeedCheck(web, {"greenhouse": source_api(JOBS, saved)})


def test_a_board_with_the_companys_jobs_exists(source_api: SourceApi, web: WebClient) -> None:
    assert check(source_api, web, "greenhouse-n26.json").exists(N26, "N26 GmbH")


def test_a_board_with_another_companys_jobs_is_not_the_companys(
    source_api: SourceApi, web: WebClient
) -> None:
    assert not check(source_api, web, "greenhouse-n26.json").exists(N26, "Zalando")


def test_a_board_that_is_not_there_does_not_exist(source_api: SourceApi, web: WebClient) -> None:
    assert not check(source_api, web, None).exists(N26, "N26")


def test_a_site_that_does_not_answer_can_not_tell() -> None:
    web = WebClient(Pacing({}, default=PaceRule(min_gap=timedelta(0))), sleep=lambda _: None)
    with pytest.raises(SourceUnavailableError):
        FeedCheck(web, {"greenhouse": "http://127.0.0.1:9"}).exists(N26, "N26")
