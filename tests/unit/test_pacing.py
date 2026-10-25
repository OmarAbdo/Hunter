from datetime import UTC, datetime, timedelta

import pytest

from hunter.domain.pacing import CapReachedError, Pacing, PaceRule

NOON = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
DEFAULT = PaceRule(min_gap=timedelta(seconds=1))


def pacing() -> Pacing:
    linkedin = PaceRule(min_gap=timedelta(minutes=2), per_day=2)
    return Pacing({"www.linkedin.com": linkedin}, default=DEFAULT)


def test_the_first_request_to_a_host_waits_for_nothing() -> None:
    assert pacing().wait("api.ashbyhq.com", NOON) == timedelta(0)


def test_the_next_request_waits_out_the_rest_of_the_gap() -> None:
    hosts = pacing()
    hosts.record("www.linkedin.com", NOON)
    assert hosts.wait("www.linkedin.com", NOON + timedelta(seconds=30)) == timedelta(seconds=90)


def test_no_wait_once_the_gap_has_passed() -> None:
    hosts = pacing()
    hosts.record("www.linkedin.com", NOON)
    assert hosts.wait("www.linkedin.com", NOON + timedelta(minutes=5)) == timedelta(0)


def test_hosts_are_paced_separately() -> None:
    hosts = pacing()
    hosts.record("www.linkedin.com", NOON)
    assert hosts.wait("api.ashbyhq.com", NOON) == timedelta(0)


def test_hosts_without_a_rule_take_the_default() -> None:
    hosts = pacing()
    hosts.record("api.ashbyhq.com", NOON)
    assert hosts.wait("api.ashbyhq.com", NOON) == timedelta(seconds=1)


def test_the_daily_cap_refuses_once_reached() -> None:
    hosts = pacing()
    hosts.record("www.linkedin.com", NOON)
    hosts.record("www.linkedin.com", NOON + timedelta(minutes=3))
    with pytest.raises(CapReachedError, match=r"www\.linkedin\.com: 2 a day"):
        hosts.wait("www.linkedin.com", NOON + timedelta(minutes=10))


def test_the_daily_cap_starts_again_the_next_day() -> None:
    hosts = pacing()
    hosts.record("www.linkedin.com", NOON)
    hosts.record("www.linkedin.com", NOON + timedelta(minutes=3))
    assert hosts.wait("www.linkedin.com", NOON + timedelta(days=1)) == timedelta(0)


def test_a_host_that_asked_for_a_pause_waits_until_it_ends() -> None:
    hosts = pacing()
    hosts.hold("apply.workable.com", NOON + timedelta(hours=21))
    assert hosts.wait("apply.workable.com", NOON) == timedelta(hours=21)
    hosts.record("apply.workable.com", NOON)
    assert hosts.wait("apply.workable.com", NOON + timedelta(hours=1)) == timedelta(hours=20)


def test_a_pause_that_has_ended_holds_nothing() -> None:
    hosts = pacing()
    hosts.hold("apply.workable.com", NOON)
    assert hosts.wait("apply.workable.com", NOON + timedelta(seconds=1)) == timedelta(0)


def test_a_shorter_pause_asked_later_does_not_end_a_longer_one() -> None:
    hosts = pacing()
    hosts.hold("apply.workable.com", NOON + timedelta(hours=2))
    hosts.hold("apply.workable.com", NOON + timedelta(minutes=1))
    assert hosts.wait("apply.workable.com", NOON) == timedelta(hours=2)
