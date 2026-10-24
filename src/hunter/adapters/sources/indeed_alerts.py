"""Indeed job-alert mails (docs/sources.md): the jobs Indeed sends to the inbox, read from the
mail's plain text. Hunter never visits indeed.com for them.

Each job in the mail is a block of lines: the title, "Company - Place", then optional salary,
employer-badge and quick-apply lines, a snippet, the age ("Vor 3 Tagen"), and the job's link."""

import re
from dataclasses import replace
from datetime import datetime, timedelta

from hunter.adapters.places import places_from_text
from hunter.domain.discovery.posting import Posting, SourceRef

SOURCE = "indeed-alert"
BLOCKS = re.compile(r"\n\s*\n")
JOB_LINK = re.compile(r"https://(?P<site>[a-z]{2,3})\.indeed\.com/(?:rc|pagead)/clk\S*")
JOB_KEY = re.compile(r"[?&]jk=(?P<key>[0-9a-f]+)")
AGE = re.compile(
    r"^(?:vor (?P<days>\d+) tag(?:en)?|(?P<days_en>\d+) days? ago|gerade geschaltet|"
    r"heute|just posted|today)$",
    re.IGNORECASE,
)
QUICK_APPLY = frozenset({"schnellbewerbung", "easily apply"})
BADGES = frozenset({"aktiver arbeitgeber", "active employer", "urgently hiring"})
SALARY = re.compile(r"[€$£]|\bpro (?:jahr|monat|stunde)\b|\ban? (?:year|month|hour)\b", re.I)
SHORTEST_BLOCK = 3


def postings_from_alert(text: str, received_at: datetime) -> list[Posting]:
    blocks = (
        [line.strip() for line in block.splitlines() if line.strip()]
        for block in BLOCKS.split(text)
    )
    return [posting for lines in blocks if (posting := posting_from(lines, received_at))]


def posting_from(lines: list[str], received_at: datetime) -> Posting | None:
    link = JOB_LINK.fullmatch(lines[-1]) if len(lines) >= SHORTEST_BLOCK else None
    if link is None:
        return None
    company, _, place_text = lines[1].rpartition(" - ")
    details = [line for line in lines[2:-1] if line.lower() not in BADGES | QUICK_APPLY]
    site = link.group("site")
    place, *other_places = places_from_text(place_text, default_country=site_country(site))
    posting = Posting(
        title=lines[0],
        company=company or lines[1],
        location=place,
        other_locations=tuple(other_places),
        source=SourceRef(source=SOURCE, native_id=""),
        description=" ".join(line for line in details if not is_salary_or_age(line)),
        posted_at=posted_at(details, received_at),
        quick_apply=any(line.lower() in QUICK_APPLY for line in lines),
    )
    return identified(posting, link.group(0), site)


def identified(posting: Posting, link: str, site: str) -> Posting:
    """A job with Indeed's job key gets its public page. A sponsored job comes without a key and
    is known by company, title and place."""
    key = JOB_KEY.search(link)
    if key is None:
        return replace(posting, source=SourceRef(source=SOURCE, native_id=posting.fuzzy_key))
    page = f"https://{site}.indeed.com/viewjob?jk={key['key']}"
    return replace(posting, source=SourceRef(source=SOURCE, native_id=key["key"]), url=page)


def site_country(site: str) -> str:
    """de.indeed.com lists jobs in Germany; www.indeed.com in the US."""
    return "US" if site == "www" else site.upper()


def is_salary_or_age(line: str) -> bool:
    return bool(SALARY.search(line) or AGE.match(line))


def posted_at(details: list[str], received_at: datetime) -> datetime | None:
    ages = (age for line in details if (age := AGE.match(line)))
    age = next(ages, None)
    if age is None:
        return None
    return received_at - timedelta(days=int(age.group("days") or age.group("days_en") or 0))
