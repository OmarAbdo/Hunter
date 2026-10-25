from datetime import UTC, datetime, timedelta

import pytest

from hunter.domain.pacing import CapReachedError, Moment, Pacing, PaceRule

NOON = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
DEFAULT = PaceRule(min_gap=timedelta(seconds=1))
HOUR = timedelta(hours=1)


def at(seconds: float, *, wall_off_by: timedelta = timedelta(0)) -> Moment:
    """`seconds` after noon on both clocks, unless the wall clock is off by some amount."""
    return Moment(wall=NOON + timedelta(seconds=seconds) + wall_off_by, steady=seconds)


def pacing() -> Pacing:
    linkedin = PaceRule(min_gap=timedelta(minutes=2), per_day=2)
    return Pacing({"www.linkedin.com": linkedin}, default=DEFAULT)


def test_the_first_request_to_a_host_waits_for_nothing() -> None:
    assert pacing().wait("api.ashbyhq.com", at(0)) == timedelta(0)


def test_the_next_request_waits_out_the_rest_of_the_gap() -> None:
    hosts = pacing()
    hosts.record("www.linkedin.com", at(0))
    assert hosts.wait("www.linkedin.com", at(30)) == timedelta(seconds=90)


def test_no_wait_once_the_gap_has_passed() -> None:
    hosts = pacing()
    hosts.record("www.linkedin.com", at(0))
    assert hosts.wait("www.linkedin.com", at(300)) == timedelta(0)


def test_a_wall_clock_set_back_does_not_lengthen_the_gap() -> None:
    """Windows corrects its clock now and then; the gap is measured on a clock that can't jump."""
    hosts = pacing()
    hosts.record("api.ashbyhq.com", at(0))
    assert hosts.wait("api.ashbyhq.com", at(0.5, wall_off_by=-HOUR)) == timedelta(seconds=0.5)


def test_a_wall_clock_set_forward_does_not_shorten_the_gap() -> None:
    hosts = pacing()
    hosts.record("api.ashbyhq.com", at(0))
    assert hosts.wait("api.ashbyhq.com", at(0.5, wall_off_by=HOUR)) == timedelta(seconds=0.5)


def test_hosts_are_paced_separately() -> None:
    hosts = pacing()
    hosts.record("www.linkedin.com", at(0))
    assert hosts.wait("api.ashbyhq.com", at(0)) == timedelta(0)


def test_hosts_without_a_rule_take_the_default() -> None:
    hosts = pacing()
    hosts.record("api.ashbyhq.com", at(0))
    assert hosts.wait("api.ashbyhq.com", at(0)) == timedelta(seconds=1)


def test_the_daily_cap_refuses_once_reached() -> None:
    hosts = pacing()
    hosts.record("www.linkedin.com", at(0))
    hosts.record("www.linkedin.com", at(180))
    with pytest.raises(CapReachedError, match=r"www\.linkedin\.com: 2 a day"):
        hosts.wait("www.linkedin.com", at(600))


def test_the_daily_cap_starts_again_the_next_day() -> None:
    hosts = pacing()
    hosts.record("www.linkedin.com", at(0))
    hosts.record("www.linkedin.com", at(180))
    assert hosts.wait("www.linkedin.com", at(86400)) == timedelta(0)


def test_a_host_that_asked_for_a_pause_waits_until_it_ends() -> None:
    hosts = pacing()
    hosts.hold("apply.workable.com", NOON + 21 * HOUR)
    assert hosts.wait("apply.workable.com", at(0)) == 21 * HOUR
    hosts.record("apply.workable.com", at(0))
    assert hosts.wait("apply.workable.com", at(3600)) == 20 * HOUR


def test_a_pause_that_has_ended_holds_nothing() -> None:
    hosts = pacing()
    hosts.hold("apply.workable.com", NOON)
    assert hosts.wait("apply.workable.com", at(1)) == timedelta(0)


def test_a_shorter_pause_asked_later_does_not_end_a_longer_one() -> None:
    hosts = pacing()
    hosts.hold("apply.workable.com", NOON + 2 * HOUR)
    hosts.hold("apply.workable.com", NOON + timedelta(minutes=1))
    assert hosts.wait("apply.workable.com", at(0)) == 2 * HOUR
