# Ads: design

Epic 2. Discovery takes jobs from many sources, but many of those sources show only a few lines of
each job, or nothing at all. Scoring a job and applying to it both need the whole ad, as the
employer wrote it. Hunter reads the missing ads one job at a time, and measures how many it has.

## The measure

Every job a campaign took is in exactly one state (`domain/ads/coverage.py`):

| State | Meaning |
|---|---|
| whole | The ad as the employer wrote it: from a feed, a details API, or a job page's schema.org `JobPosting` |
| snippet | The few lines a search shows (Adzuna, Careerjet, Indeed alerts, Jooble, USAJobs) |
| none | No text yet |
| gone | The job was taken down, with evidence: a 404, a "no longer available" page, or its board no longer listing it |

Whether a text is the whole ad is a fact about where it came from, not its length: an employer's
feed gives the whole ad however short it is, and an ad read from the job's own page is whole even
for a source whose search shows only snippets (the `whole_ads` table records those reads).

The share that counts is **whole ads of the open jobs**, those not gone. Epic 2's target: at least
95%, with every taken job in one of the four states. `hunter ads` prints it by source, and the
window's Ads tab shows the same table. The Jobs tab marks each job's state, and a click on it opens
the ad.

## Reading the ads

Every discovery run ends by reading the ads its taken jobs still lack, newest first
(`application/read_ads.py`, wired in `adapters/ad_reading.py`). Before that, the jobs its boards no
longer list are marked gone. Each source has its own reader:

| Source | How its ad is read |
|---|---|
| Bundesagentur | Its details API, `pc/v4/jobdetails/<base64 reference>`; 404 means gone |
| SmartRecruiters | The posting's details, `/v1/companies/<board>/postings/<id>`, section by section; 404 means gone |
| softgarden | The job's page, its `JobPosting`, over plain HTTP where robots.txt allows; 404 means gone |
| Personio | The job's page: its `JobPosting`, or else its ad sections (`jb-description-item`), for boards whose feed leaves the ads out |
| StepStone and XING alerts | The alert link's first hop, read without following it, names the job's public page: inside StepStone's magic link (`returnUrl`) or XING's login hop (`dest_url`). The sign-in hop is never opened. Headless Edge reads the public page logged out |
| Adzuna | Its details page (`adzuna.de/details/<id>`) through headless Edge, since plain requests get 403 |
| LinkedIn alerts | LinkedIn's public guest page, `linkedin.com/jobs-guest/jobs/api/jobPosting/<job id>`, read logged out with a browser's identity, one every 8 seconds. Only the job id comes from the mail, whose links are never opened. "No longer accepting applications" or a 404 means gone |
| Careerjet and Indeed alerts | The employer's own ad, by web search (below), because their own pages can't be read: Careerjet's links are billed clicks, Indeed asks for a sign-in |
| EURES and the employers' feeds | Their jobs come with the whole ad already |

A job read again from any source takes the fuller ad: a snippet over nothing, the whole ad over a
snippet. A job first seen on a job board becomes the employer's job once its board shows it, and
keeps the whole ad it has if the employer's feed carries none.

Pages read through Edge use Hunter's own profile in `var/edge-ads`. They say a job is gone in
words: "isn't available", "nicht mehr verfügbar", "nicht mehr aktuell", "Page not found", "Seite
nicht gefunden".

## Gone jobs

A job is gone when its reader gets a 404 or a "no longer there" page, or when a run read its board
in full and the board no longer listed it. "In full" means the read worked, brought jobs, and
stayed below its system's cut-off: SmartRecruiters stops at 1,000 jobs, Workday at 200, onlyfy at
300, and rexx can miss any single job's page, so its boards never count. A gone job its own board
lists again is open again.

## The employer's own ad, by web search

For Careerjet and Indeed jobs (`adapters/sources/searches/employer_search.py`): a search
for `"<company>" <title>` through Edge, on the engine whose turn it is (see docs/sources.md). The
results that aren't job boards or job aggregators are read, the first eight of each answer, over
plain HTTP with a browser's identity (through Edge only where a site refuses), and the first whose
`JobPosting` names the job's title and company (Hunter's identity keys: gender markers and legal
forms don't count) is its ad (`domain/ads/employer_ad.py`). A near miss is no ad: the wrong ad is
worse than none. Many of the ads found are copies on job-copy sites, which publish the employer's
ad under the employer's name.

An answer without a fitting ad is followed at once by another search, which goes to the next
engine and brings other results; a job gets three answered searches a week at most, then waits.
While every engine rests, the job waits for a later run.
