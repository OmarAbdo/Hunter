# Discovery: design

Discovery fills one pool of jobs from every source, and decides which campaigns each job belongs to.
It's the first part of Hunter. Preparing applications and applying come after it and read from the
pool. The sources are in [sources.md](sources.md).

## What went wrong before, and the rule against it

HQ found far more jobs than it could process. 1,328 of its 1,600 Bundesagentur jobs never reached
sorting, and nothing showed the backlog growing. In Hunter:
- every source's yield is counted;
- each campaign's backlog is visible and bounded;
- discovery only adds jobs to a pool. Nothing downstream is forced to keep up with it.

## The flow

```
sources ──fetch──> postings ──normalise──> pool (jobs + sightings) ──match──> campaign matches
   ^                                          │
   └──── company registry <──── links, names ─┘
```

1. **Fetch:** each source returns raw postings in its own shape.
2. **Normalise:** every adapter maps its postings to one `Posting`, with a structured `Location`.
3. **Pool:**
   - Each posting becomes a job, or is recognised as one Hunter already has.
   - Each time a source shows it, Hunter adds a **sighting**: one job seen on Greenhouse, in an
     Indeed alert and on EURES is one job with three sightings.
4. **Registry:** every ATS link and every company name Hunter sees updates the company registry.
   A company's feed, once known, is read on every run.
5. **Match:** each new job is checked against every active campaign by plain code. The result is a
   match with a verdict and its reason, or no match. Jobs that match no campaign stay in the pool
   for campaigns added later.

## The domain (pure logic, standard library only)

- **`Posting`:**
  - title, company name, `Location`, employment type, description, URLs;
  - when it was posted;
  - `SourceRef` (which source, and the source's own id).
- **`Location`:**
  - country (ISO 3166 code) and city;
  - workplace (onsite, hybrid, remote);
  - for remote jobs, a **remote scope**: the countries or regions allowed to apply.
  - Sources' own structured fields come first, then an offline place-name dataset. An AI step reads
    free text only as a last resort, as a doctrine AI task with an eval set.
- **Job identity, two keys:**
  - the **exact key** from the employer's own system: `ats:board:job-id`;
  - the **fuzzy key** for postings without one: normalised company, normalised title, place.
  - A posting from a job board can be linked to the employer's posting later; the job then has both.
- **`Company`:** a normalised name key, its known boards (`ats`, `board`), each board's feed status,
  and where it came from.
- **`Campaign`:**
  - its criteria: countries and remote scope, role families (title patterns), employment types,
    languages, how fresh a job must be;
  - which sources and searches it uses.
  - `matches(job)` gives a verdict with its reason, so every rejection can be explained and counted.
- **`Yield`:** per source and run: fetched, new jobs, sightings, matched per campaign. Applied comes
  later.

## Application layer (use cases)

- `discover(sources)`: fetch, normalise, add to the pool, update the registry, match, record the
  yield. Each source is bounded per run (pages, requests).
- `probe(company)`: find the company's board ([sources.md](sources.md), "Finding a company's board").
- `resolve(job)`: link a job-board posting (an Indeed alert, say) to the employer's own posting.

Ports, kept small: `JobSource` (fetch postings), `Pool` (store and find jobs, sightings, companies),
`Mailbox` (new mails since a mark), `Clock`.

## Adapters

- **One module per source.** Each is tested against a saved real response in `tests/fixtures/`.
- **HTTP:** one client with a timeout on every call, a minimum gap and a daily cap per host, and
  `robots.txt` checks for page reads.
- **Mail:** IMAP with an app password for each of the two inboxes. Hunter keeps a mark per inbox and
  sender, so each mail is read once.
- **Storage:** SQLite (standard library) in `var/hunter.db`. `var/` is gitignored because it's
  personal data. This repository is public: nothing personal is ever committed. That covers the CV,
  facts, mail contents, and the credentials in `var/accounts.toml`.
- **Command line:** `python -m hunter discover --campaign <id>` prints the yield per source.

## Running it

From the project folder: `hunter` in cmd, `.\hunter` in PowerShell (which doesn't run programs
from the current folder without `.\`), `./hunter.sh` in Git Bash.

```
hunter boards add https://job-boards.greenhouse.io/n26 --company N26
hunter discover                          # every campaign in campaigns/
hunter discover --campaign de-swe-berlin
```

A line for each source is printed as soon as it's read; a full run takes about a minute. Then
comes the report: each source's fetched, new and taken counts, and each campaign's rejections by
reason. Ctrl+C stops a run, and what was read until then is kept. The first run needs the
project's environment: `doctrine check` builds it once.

## Campaigns

One file each, `campaigns/<id>.toml`, holding criteria and sources, and nothing personal. The pilot
is `de-swe-berlin`: full-time software jobs in Berlin (onsite or hybrid), and remote jobs open to
Germany.

## Build order (one item each)

1. **Domain:** `Posting`, `Location`, job keys, `Company`, `Campaign` and matching.
2. **Pool:** SQLite storage for jobs, sightings and companies.
3. **HTTP client** with pacing, plus the first feeds: Greenhouse and Ashby.
4. **Discovery:** the `discover` use case, the command line and the yield report; the pilot
   campaign.
5. **The other feeds:** Lever, Workable, Personio, SmartRecruiters, Recruitee, Teamtailor, Workday.
6. **Probing:** finding a company's board.
7. **Mail:** the IMAP reader and the Indeed alert parser, then `resolve`.
8. **Searches:** Bundesagentur, EURES, UN Careers; then the keyed ones once there are keys.
9. **Further alert parsers:** LinkedIn, StepStone, XING, Bayt and others, each when its mails
   arrive.
