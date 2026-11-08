from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hunter.adapters.mail.mailbox import Mail
from hunter.adapters.sources.alerts.linkedin import SENDER, LinkedInAlerts, postings_from_alert
from hunter.adapters.sources.alerts.linkedin_ads import LinkedInAds
from hunter.adapters.web_client import WebClient
from hunter.application.ports import SourceUnavailableError
from hunter.domain.discovery.location import Location, Workplace
from hunter.domain.discovery.posting import Posting, SourceRef

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "sources"
WITH_A_COUNT = (FIXTURES / "linkedin-alert-a.txt").read_text(encoding="utf-8")
HEADING_ABOVE_THE_FIRST_JOB = (FIXTURES / "linkedin-alert-b.txt").read_text(encoding="utf-8")
RECEIVED = datetime(2026, 10, 28, 8, 7, tzinfo=UTC)
JOB_PAGE = "https://www.linkedin.com/comm/jobs/view/4484217216/?trackingId=the-id"
KEEP_THE_ALERT_ON = """Do you still want job alerts for Web Developer in Berlin, Berlin, Germany?
We noticed you haven't checked this job alert in over 3 months.
Keep job alert on: https://www.linkedin.com/comm/jobs/search-results/?keywords=Web&origin=COOL_OFF
Not receiving the right jobs?
Create a new alert to hear about the latest jobs that match your interests.
Create new job alert: https://www.linkedin.com/jobs/search-results/?lipi=the-page-id

----------------------------------------

You are receiving Job Alert emails."""
ALERT_CREATED = """Your job alert for Web Developer in Berlin has been created
You'll receive notifications when new jobs are posted that match your search preferences.
See all jobs on LinkedIn:  https://www.linkedin.com/comm/jobs/search-results/?keywords=Web"""
ALERT_TURNED_OFF = """We've turned off your job alert for Web Developer in Berlin
Create new job alert: https://www.linkedin.com/jobs/search-results/?lipi=the-page-id"""


def job(place: str, link: str = JOB_PAGE, mark: str = "") -> str:
    return f"Backend Engineer\nCloudworkz\n{place}\n{mark}\nView job: {link}\n\n{'-' * 57}\n"


def test_every_job_in_the_alert_becomes_a_posting() -> None:
    postings = postings_from_alert(WITH_A_COUNT)
    assert [posting.company for posting in postings] == ["Cloudworkz", "ML6", "AVIV Group"]
    first = postings[0]
    assert first.title == "Senior Backend Application Engineer – Python / AWS / GenAI"
    assert first.location == Location(country="DE")
    assert first.posted_at is None


def test_the_alerts_own_lines_are_no_part_of_a_job() -> None:
    first, second = postings_from_alert(HEADING_ABOVE_THE_FIRST_JOB)
    assert first.title == "Volontär*in Content Editing Books - Humanities (m/w/d)"
    assert first.company == "De Gruyter Brill"
    assert first.location == Location(country="DE", city="Berlin")
    assert second.company == "Stiftung Preußischer Kulturbesitz"


def test_a_line_about_the_company_is_not_its_place() -> None:
    hiring = postings_from_alert(WITH_A_COUNT)[1]
    assert hiring.location == Location(country="DE", city="Berlin")


def test_a_job_is_known_by_linkedins_id_and_its_clean_page() -> None:
    first = postings_from_alert(WITH_A_COUNT)[0]
    assert first.source == SourceRef(source="linkedin-alert", native_id="4484217216")
    assert first.url == "https://www.linkedin.com/jobs/view/4484217216/"
    assert first.apply_url is None


def test_a_link_naming_the_job_in_its_query_gives_the_same_page() -> None:
    link = "https://www.linkedin.com/comm/jobs/search/?currentJobId=4483267177&refId=the-id"
    [posting] = postings_from_alert(job("Berlin", link))
    assert posting.source.native_id == "4483267177"
    assert posting.url == "https://www.linkedin.com/jobs/view/4483267177/"


def test_nothing_of_the_mails_links_is_kept_but_the_job_id() -> None:
    """Those links can log in as Omar: their tokens must not reach the pool."""
    kept = repr(
        postings_from_alert(WITH_A_COUNT) + postings_from_alert(HEADING_ABOVE_THE_FIRST_JOB)
    )
    for token in ("the-login-token", "the-member-token", "the-tracking", "the-ref-id", "/comm/"):
        assert token not in kept


def test_the_quick_apply_mark_is_kept() -> None:
    marked = [posting.quick_apply for posting in postings_from_alert(WITH_A_COUNT)]
    assert marked == [True, False, False]


def test_the_older_name_of_quick_apply_is_read_too() -> None:
    [posting] = postings_from_alert(job("Berlin", mark="Easy Apply"))
    assert posting.quick_apply is True


@pytest.mark.parametrize(
    ("place", "location"),
    [
        ("Berlin (Hybrid)", Location("DE", "Berlin", Workplace.HYBRID)),
        ("Germany (Remote)", Location("DE", None, Workplace.REMOTE, frozenset({"DE"}))),
        ("Berlin, Germany (On-site)", Location("DE", "Berlin", Workplace.ONSITE)),
        ("Berlin (On-site)", Location("DE", "Berlin", Workplace.ONSITE)),
        ("European Union (Remote)", Location(None, None, Workplace.REMOTE, frozenset({"EU"}))),
        ("European Union", Location()),
        ("Munich, Bavaria, Germany", Location("DE", "Munich")),
    ],
)
def test_a_jobs_place_and_workplace(place: str, location: Location) -> None:
    [posting] = postings_from_alert(job(place))
    assert posting.location == location


def test_a_job_in_two_towns_is_open_in_both() -> None:
    [posting] = postings_from_alert(job("Berlin, Hamburg"))
    assert [place.city for place in posting.locations] == ["Berlin", "Hamburg"]


@pytest.mark.parametrize("text", [KEEP_THE_ALERT_ON, ALERT_CREATED, ALERT_TURNED_OFF, ""])
def test_a_mail_without_a_job_list_gives_no_jobs(text: str) -> None:
    assert postings_from_alert(text) == []


class StandInMailbox:
    def __init__(self, mails: list[Mail], *, down: bool = False) -> None:
        self.mails = mails
        self.down = down
        self.remembered: list[Mail] = []

    def new_mails(self, sender: str) -> list[Mail]:
        if self.down:
            raise OSError("imap.gmail.com: connection refused")
        return self.mails if sender == SENDER else []

    def remember(self, sender: str, mails: list[Mail]) -> None:
        self.remembered = mails


def test_the_alert_source_reads_every_inbox_and_remembers_what_it_read() -> None:
    jobs = Mail(uid=3, validity=7, received_at=RECEIVED, text=WITH_A_COUNT)
    no_jobs = Mail(uid=4, validity=7, received_at=RECEIVED, text=KEEP_THE_ALERT_ON)
    more = Mail(uid=5, validity=7, received_at=RECEIVED, text=HEADING_ABOVE_THE_FIRST_JOB)
    one, other = StandInMailbox([jobs, no_jobs, more]), StandInMailbox([])
    postings = LinkedInAlerts([one, other]).fetch()
    assert len(postings) == 5
    assert one.remembered == [jobs, no_jobs, more]


def test_an_inbox_that_cannot_be_read_makes_the_source_unavailable() -> None:
    with pytest.raises(SourceUnavailableError, match="connection refused"):
        LinkedInAlerts([StandInMailbox([], down=True)]).fetch()
    assert LinkedInAlerts([]).name == "linkedin-alert"


def html_of(*jobs: tuple[str, str, str]) -> str:
    """The HTML part's shape: a job's links, then its title, and "Company · Place (Workplace)"."""
    return "".join(
        f'<a href="https://www.linkedin.com/comm/jobs/view/{job_id}/?midToken=the-token">logo</a>'
        f'<a href="https://www.linkedin.com/comm/jobs/view/{job_id}/?midToken=the-token">'
        f"<p>{title}</p><p>{place}</p></a>"
        for job_id, title, place in jobs
    )


def alert(job_id: str, place: str) -> str:
    return (
        f"Backend Engineer\nLegalhero\n{place}\n"
        f"View job: https://www.linkedin.com/comm/jobs/view/{job_id}/?midToken=the-token\n"
        f"{'-' * 40}\n"
    )


@pytest.mark.parametrize(
    ("shown", "workplace"),
    [
        ("Legalhero &middot; Berlin (Hybrid)", Workplace.HYBRID),
        ("Legalhero &middot; Berlin (On-site)", Workplace.ONSITE),
        ("Legalhero · Berlin (Remote)", Workplace.REMOTE),
    ],
)
def test_a_job_s_workplace_comes_from_the_mail_s_html(shown: str, workplace: Workplace) -> None:
    html = html_of(("111", "Backend Engineer", shown))
    [posting] = postings_from_alert(alert("111", "Berlin"), html)
    assert posting.location.workplace is workplace
    assert posting.location.city == "Berlin"


def test_each_job_gets_its_own_workplace() -> None:
    html = html_of(
        ("111", "Hybrid Cloud Engineer", "Legalhero &middot; Berlin (On-site)"),
        ("222", "Backend Engineer", "CHECK24 &middot; Germany (Remote)"),
    )
    first, second = postings_from_alert(alert("111", "Berlin") + alert("222", "Germany"), html)
    assert first.location.workplace is Workplace.ONSITE
    assert second.location.workplace is Workplace.REMOTE


def test_a_job_the_html_says_nothing_about_keeps_what_the_plain_text_says() -> None:
    [posting] = postings_from_alert(alert("111", "Berlin"), html_of(("222", "x", "y (Remote)")))
    assert posting.location.workplace is None


def test_the_workplace_is_read_from_real_mails_through_the_source() -> None:
    mail = Mail(
        1,
        7,
        RECEIVED,
        alert("111", "Berlin"),
        html_of(("111", "Backend Engineer", "Legalhero &middot; Berlin (Hybrid)")),
    )

    class OneMail:
        def new_mails(self, sender: str) -> list[Mail]:
            return [mail]

        def remember(self, sender: str, mails: list[Mail]) -> None:
            return

    [posting] = LinkedInAlerts([OneMail()]).fetch()
    assert posting.location.workplace is Workplace.HYBRID


GUEST = "/jobs-guest/jobs/api/jobPosting/4484669674"


SourceApi = Callable[[str, str | None], str]


def guest_reader(source_api: SourceApi, web: WebClient, saved: str | None) -> LinkedInAds:
    return LinkedInAds(web, api=source_api(GUEST, saved))


def delta_job() -> Posting:
    return Posting(
        title="Senior AI Product Engineer (Berlin)",
        company="The Delta",
        location=Location(country="DE", city="Berlin"),
        source=SourceRef(source="linkedin-alert", native_id="4484669674"),
    )


def test_a_job_s_ad_is_read_from_linkedin_s_public_guest_page(
    source_api: SourceApi, web: WebClient
) -> None:
    ad = guest_reader(source_api, web, "linkedin-guest-live.html").read(delta_job())
    assert ad.startswith("Are you an engineer who loves owning the product")
    assert ad.endswith("Ready? Hit apply and get the full Job Profile")


@pytest.mark.parametrize("saved", ["linkedin-guest-closed.html", None])
def test_a_job_no_longer_accepting_applications_or_not_found_is_gone(
    source_api: SourceApi, web: WebClient, saved: str | None
) -> None:
    with pytest.raises(SourceUnavailableError) as raised:
        guest_reader(source_api, web, saved).read(delta_job())
    assert raised.value.gone
