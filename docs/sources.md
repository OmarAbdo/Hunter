# Job sources

Where Hunter finds jobs and how it gets each source's data. Checked live on 2026-10-24. Re-check a
source before building its adapter, because access rules change.

## Rules every source follows

- **No paid sources.** A free API key that needs a sign-up is fine.
- **Automation is judged by risk, not by principle.** Browser automation, computer use and
  getting past a captcha are fine wherever they work and can't backfire. Where a harsh penalty is
  likely, they're out: an account ban, or a block on a site Omar depends on, LinkedIn above all.
  Those sites are read through their own channels: alert mails, and human-paced use.
  `robots.txt` is respected wherever Hunter reads public pages.
- **Sites without an API come in through their own job-alert emails.** The site sends them to the
  inbox; Hunter reads the inbox.
- **Apply on the employer's own system where possible.** A job seen on a job board (LinkedIn, Indeed,
  StepStone) is traced back to the employer's own posting. That's where Hunter can apply, and the
  employer joins the company registry.
- **Every source has to earn its place.** Hunter counts each source's jobs found, matched to a
  campaign and applied to. A source that never leads to an application is dropped.

## Rate limits

What each source publishes about how often it may be asked, checked on 2026-10-25 in its docs and
in its answers' headers. Hunter's own pace is in `PACES` (`adapters/sources/feed_table.py`): one
request a second per host unless a source needs less. A `Retry-After` is always honoured; a site
asking for more than 10 minutes isn't asked again in that run.

| Source | What it publishes | Seen | Hunter's pace |
|---|---|---|---|
| Greenhouse (Job Board API) | No limit published | No rate headers | 1 a second |
| Ashby (posting API) | No limit published | No rate headers | 1 a second |
| Lever (postings API) | No limit for reading; 2 applications a second; its key API allows 10 a second | No rate headers | 1 a second |
| Workable (public widget API) | No limit published; its key API allows 10 per 10 seconds | 429 after about 16 requests a second apart; after a day of probing, `Retry-After: 75335` (21 hours) for the whole host | 1 per 10 seconds, 100 a day; never guessed when probing |
| Personio (XML feed) | No limit for the feed; 100 applications a minute per IP | No rate headers | 1 a second |
| SmartRecruiters | 10 requests a second and 8 at once (its customer API) | No rate headers | 1 a second |
| Recruitee (careers site API) | No limit published | No rate headers | 1 a second |
| Teamtailor | 50 requests per 10 seconds (its key API; the RSS feed says nothing) | No rate headers | 1 a second |
| Workday | No limit published | No rate headers | 1 a second |
| Bundesagentur | Nothing official; a third-party listing says 1,000 an hour | No rate headers | 1 a second |
| EURES | No limit published | No rate headers | 1 a second |

## Access kinds

| Kind | What it is |
|---|---|
| Feed | One company's job board on an applicant tracking system (ATS); public, no key |
| Search | A public search API over many employers |
| Keyed search | A search API that needs a free key |
| Alert mail | Job-alert emails the site sends to one of the two inboxes |
| Page data | `schema.org/JobPosting` data that career pages publish for search engines |

## Sources

| Source | Kind | Live check | Campaigns | Notes |
|---|---|---|---|---|
| Greenhouse | Feed: `boards-api.greenhouse.io/v1/boards/{board}/jobs` | 200 | All | Global feeds; HQ's best route to applications |
| Ashby | Feed: `api.ashbyhq.com/posting-api/job-board/{board}` | 200 | All | Remote flag, compensation; HQ's best yield |
| Lever | Feed: `api.lever.co/v0/postings/{board}?mode=json` (EU: `api.eu.lever.co`) | 200 | All | Country, workplace type |
| Workable | Feed: `apply.workable.com/api/v1/widget/accounts/{board}` | 404 for a missing account | All | |
| Personio | Feed: `{board}.jobs.personio.{de,com}/xml` | Known from HQ | DE, EU | XML |
| SmartRecruiters | Feed: `api.smartrecruiters.com/v1/companies/{id}/postings` | 200 | All | Case-sensitive company id |
| Recruitee | Feed: `{board}.recruitee.com/api/offers/` | 200 | All | Not in HQ |
| Teamtailor | Feed: `{board}.teamtailor.com/jobs.rss` | 200 | All | Not in HQ |
| Workday | Feed: `POST {tenant}.wd{n}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` | 200 | All, mostly large employers | Not in HQ |
| JOIN | Alert and confirmation mails | Pages publish no job data | DE | No public feed found |
| Bundesagentur für Arbeit | Search: `rest.arbeitsagentur.de/.../pc/v6/jobs`, header `X-API-Key: jobboerse-jobsuche` | 200 | DE | Built. Jobs within 25 km of the place, published in the last 30 days, 100 a page. No descriptions in the list. About two thirds are applied to on arbeitsagentur.de; the rest link to other job boards (jobexport, gute-jobs, get-in-it), rarely to the employer's own system |
| EURES | Search: `POST europa.eu/eures/api/jv-searchengine/public/jv-search/search` | 200 | Every EU campaign | Built. Title search, last month, 50 a page; the place is a country or NUTS code (`nl`, `de3`). German jobs are the Bundesagentur's own (the id holds its reference), so they join those jobs; about half name the employer's website. Elsewhere jobs rarely name the employer, and only the region is given: 1,567 of 2,000 Dutch jobs got no city |
| UN Careers | Search: `careers.un.org/api/public/opening/jo/list/filteredV2/en` | 200 | Culture, diplomacy, internships | |
| Arbeitnow | Search: `www.arbeitnow.com/api/job-board-api` | 200 | DE | |
| Himalayas, Remotive, We Work Remotely | Search (API or RSS) | 200 | Remote, US part-time | Remote only |
| USAJobs | Keyed search: `data.usajobs.gov/api/search` | 401 without a key | US | US government jobs only |
| Adzuna, Jooble, Careerjet | Keyed search | 400 or 401 without a key | US, UAE, EU | Aggregators; keys pending |
| Indeed (Glassdoor is part of Indeed) | Alert mail from `donotreply@jobalert.indeed.com` | Arriving: several a day, up to about 20 jobs each | DE, US, UAE | Each job has title, company, place, salary, freshness, Indeed's job key and its quick-apply mark ("Schnellbewerbung") |
| LinkedIn | Alert mail | None in the main inbox; check the jobs inbox | All | |
| StepStone, XING | Alert mail | Not set up yet | DE | StepStone's `robots.txt` disallows its search pages |
| Bayt, GulfTalent, Naukrigulf | Alert mail | Not set up yet | UAE | Bayt's `robots.txt` disallows its job lists |
| Employer career pages | Page data | | All | For employers on no known ATS |
| Hunter's own inboxes | Confirmations, recruiter mails, "jobs for you" mails | | All | Companies for the registry |

No ATS publishes a sitemap that lists all of its companies (checked for Ashby, Greenhouse, Lever,
Workable, JOIN and SmartRecruiters). Companies come in one at a time, through the registry.

## Finding a company's board

The company registry grows from every company name and every link Hunter sees. For a company
without a known board, Hunter looks in this order:
1. **Links:** a link to an ATS on any job or in any mail names the board directly.
2. **Likely board names:** Hunter tries them on every feed above.
3. **The company's careers page:** Hunter looks for ATS links and `JobPosting` data.
4. **A web search:** an AI step using Claude's own WebSearch, last.

## What's still to do outside the code

- **Free API keys** for Adzuna, Jooble, Careerjet and USAJobs (Omar signs up).
- **App passwords for both inboxes**, for Hunter's mail reader (IMAP).
- **Job alerts on each site:** set up by hand, from a list Hunter generates for each campaign.
