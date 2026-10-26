# Job sources

Where Hunter finds jobs and how it gets each source's data. Checked live on 2026-10-24. Re-check a
source before building its adapter, because access rules change.

## Rules every source follows

- **No paid sources.** A free API key that needs a sign-up is fine.
- **Automation is judged by risk, not by principle.** Browser automation, computer use and
  getting past a captcha are fine wherever they work and can't backfire. Where a harsh penalty is
  likely, they're out: an account ban, or a block on a site Omar depends on, LinkedIn above all.
  Those sites are read through their own channels: alert mails, and human-paced use.
- **Sites that turn bots away are read anyway, by better means.** Where a site welcomes bots,
  Hunter names itself (`Hunter/0.1 (personal job search)`) and follows its `robots.txt`. Where a
  site turns bots away (its `robots.txt`, a 403, a challenge page), Hunter doesn't give up on its
  jobs: it reads them with a browser's identity, through a real browser, or by another route. It
  stays politely paced either way, and the penalty rule above still decides what's too risky.
  Portals limiting what they get and Hunter trying to send more applications are both fair; the
  conflict is solved with smarter methods, not by giving up.
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
| d.vinci (job publication list) | No limit published | No rate headers | 1 a second |
| coveto (RSS) | No limit published | No rate headers | 1 a second |
| softgarden (list page) | No limit published | No rate headers | 1 a second |
| onlyfy (list page) | `Crawl-delay: 1` in robots.txt | No rate headers | 1 a second |
| SuccessFactors (RSS) | No limit published | No rate headers | 1 a second |
| rexx (list and job pages) | No limit published | No rate headers | 1 a second |
| Adzuna | Plan limits shown in the account; free plans allow about 25 a minute and 250 a day | No rate headers | 1 per 3 seconds, 250 a day |
| Bundesagentur | Nothing official; a third-party listing says 1,000 an hour | No rate headers | 1 a second |
| Careerjet | No limit published | No rate headers | 1 a second |
| USAJobs | No request rate published; at most 500 jobs a page and 10,000 a search | No rate headers | 1 a second |
| UN Careers | No limit published | No rate headers; `cache-control: max-age=900` | 1 a second |
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
| d.vinci | Feed: `{board}.dvinci-easy.com/jobPublication/list.json` | 200; a missing portal doesn't resolve | DE, AT | Built. German ATS. One portal can hold a group's companies; one opening can have several ads. Not guessed when probing: a missing portal gives no answer at all, so a guess can't be told from a site that's down |
| coveto | Feed: RSS at `{board}.coveto.de/public/rss/` (`k11145`) | 200 | DE | Built. German ATS, used mostly by staffing agencies. The place is a line of the description; job pages are on the company's own domain. Not guessed: boards are numbered |
| softgarden | Page: the vacancy list at `{board}.softgarden.io/de/vacancies` | 200; 404 for a missing board | DE | Built. German ATS; no feed, so the list page is read where robots.txt allows (it bars only `/api/` and the recruiters' pages). Each board picks its columns: title always, mostly the date and places, on a group's board the company |
| onlyfy (was Prescreen) | Page: the job list at `{board}.onlyfy.jobs/?page=N`, 10 a page | 200; 404 for a missing board | DE, AT | Built. German-speaking ATS (XING's); no feed, robots.txt allows the list (`Crawl-delay: 1`). Each card has the title and a line of facts: the town first, the employment type, the date |
| SAP SuccessFactors | Feed: RSS at `{host}/sitemal.xml` on a Career Site Builder site (`jobs.bechtle.com`) | 200; 404 where there's none | All, mostly large employers | Built. Undocumented by SAP but on every such site. The board is the site's host, known from its job links (`/job/<title>/<id>/`). Sites on SuccessFactors' own `career*.successfactors.*` hosts (Recruiting without Career Site Builder) have no feed. Not guessed |
| rexx | Page: the job list at `{board}-portal.rexx-recruitment.com/stellenangebote.html`, 100 a page, then each job's page | 200; 404 for a missing portal | DE | Built. German ATS. Each company styles its list differently, so only the job links (`-j<id>.html`, often on the company's own domain) are taken from it; each job's page gives schema.org `JobPosting` data. One request per job, up to 500. Its `robots.txt` bars named scraping libraries; Hunter isn't one of them. Not guessed |
| JOIN | Alert and confirmation mails | Pages publish no job data | DE | No public feed found |
| Bundesagentur für Arbeit | Search: `rest.arbeitsagentur.de/.../pc/v6/jobs`, header `X-API-Key: jobboerse-jobsuche` | 200 | DE | Built. Jobs within 25 km of the place, published in the last 30 days, 100 a page. No descriptions in the list. About two thirds are applied to on arbeitsagentur.de; the rest link to other job boards (jobexport, gute-jobs, get-in-it), rarely to the employer's own system |
| EURES | Search: `POST europa.eu/eures/api/jv-searchengine/public/jv-search/search` | 200 | Every EU campaign | Built. Title search, last month, 50 a page; the place is a country or NUTS code (`nl`, `de3`). German jobs are the Bundesagentur's own (the id holds its reference), so they join those jobs; about half name the employer's website. Elsewhere jobs rarely name the employer, and only the region is given: 1,567 of 2,000 Dutch jobs got no city |
| UN Careers | Search: `POST careers.un.org/api/public/opening/jo/list/filteredV2/en`, 100 a page from page 0; duty stations from `GET …/jo-filter/list/v2/en` | 200; no robots.txt (the path serves the app) | Culture, diplomacy, internships | Built. The UN Secretariat's open jobs; no key. The query is matched as one phrase in a job's text, duty station included. A campaign's place is a duty station ("Geneva", "New York", "Nairobi") or a country as the UN writes it ("Kenya", "United States of America"); empty means every station. Up to 300 jobs, newest first. The company is the UN entity, and the title carries the grade; internships and consultancies are marked, and a home-based work location makes a job remote |
| Arbeitnow | Search: `www.arbeitnow.com/api/job-board-api` | 200 | DE | |
| Himalayas, Remotive, We Work Remotely | Search (API or RSS) | 200 | Remote, US part-time | Remote only |
| USAJobs | Keyed search: `data.usajobs.gov/api/search`, headers `User-Agent: <account mail>` and `Authorization-Key` | 200 with Omar's key | US | Built. US government jobs, at home and at posts abroad. Last 30 days, the place as `LocationName`, 100 a page, up to 3 pages. Every place a job names, read by its city alone, since states share names with towns; remote where marked, hybrid where telework is allowed. Links go to the job's usajobs.gov page, where it's applied to |
| Adzuna | Keyed search: `api.adzuna.com/v1/api/jobs/{country}/search/{page}` | 200 with Omar's key | Its countries: DE, GB, US, NL, FR, AT, CH, ... (not UAE) | Built. An aggregator; needs a country per search; last 30 days, 50 a page, up to 4 pages. Links go to Adzuna's page for the job, without the tracking query that carries the app id |
| Jooble | Keyed search: `POST jooble.org/api/{key}` | 200 with Omar's key | US with this key; others need their own | Built. 20 a page, up to 5 pages. Keys are per country site: Omar's is for jooble.org, and `de.jooble.org` refuses it (403). A search for "Berlin" brings jobs placed only in "Germany", so a city campaign rejects them; a German key would fix that |
| Careerjet | Keyed search: `search.api.careerjet.net/v4/query`, Basic auth with the key and the key's referer | 200 with Omar's key | DE, GB, US, AE, NL, AT, CH, FR, ES and about 60 more | Built. An aggregator; needs a country per search, which picks its locale (`de_DE`). 50 a page (`pagesize`; the documented `page_size` is ignored), up to 6 pages. Jobs have no ids, and their `jobviewtrack.com` links change with every answer, so a job is known by company, title and place. A place it can't tell apart runs no search |
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
2. **The company's careers page** (built), where its website is known. Today EURES is the only
   source that gives the website. Hunter reads the home page and up to two of the site's own
   pages it calls careers ("Karriere", "Jobs"), and tries every board they link to, embed or name
   in their code, first. A company is probed again once it gains a website. `JobPosting` data on
   the pages isn't read yet.
3. **Likely board names:** Hunter tries them on every system that answers a missing board with a
   404: Greenhouse, Ashby, Lever, Recruitee, Teamtailor, softgarden, onlyfy, Personio and
   SmartRecruiters. Workable isn't guessed.
4. **A web search:** an AI step using Claude's own WebSearch, last.

## What's still to do outside the code

- **Free API keys** for Adzuna, Jooble, Careerjet and USAJobs: done; they're in `var/accounts.toml`.
- **App passwords for both inboxes**, for Hunter's mail reader (IMAP).
- **Job alerts on each site:** set up by hand, from a list Hunter generates for each campaign.
