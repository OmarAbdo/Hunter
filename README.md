<p align="center">
  <img src="src/hunter/adapters/gui/static/hunter.svg" alt="Hunter's icon" width="128" height="128">
</p>

<h1 align="center">Hunter</h1>

<p align="center">Omar's own job search, run by a program: it finds the jobs, and later applies to them.</p>

Hunter's first part is **discovery**. It reads job sources into one local pool: company job
boards, public job searches and job-alert mails. Each campaign then takes the jobs it wants, for
example full-time software jobs in Berlin. Preparing and sending applications come next.

## Using it

Hunter runs on Windows, from this folder.

- **Hunter's window:** run `hunter shortcuts` once. It puts a Hunter icon on the desktop and in the
  Start menu. The icon opens Hunter's window, which shows the jobs each campaign took, the
  companies and their boards, and the discovery runs. A run can be started from the window too.
- **From a console:** `hunter discover` reads every source for every campaign and prints what each
  source brought. `hunter boards add <link> --company <name>` adds a company's job board, and
  `hunter boards probe` looks for the boards of companies known only by name.

Personal data stays in `var/` (the job pool, mail and API keys) and is never committed.

## Where to read more

- [docs/discovery.md](docs/discovery.md): how discovery works, campaigns, and how to run it.
- [docs/sources.md](docs/sources.md): every source, its limits, and the rules Hunter follows on
  other people's sites.
- [docs/agents.md](docs/agents.md): the briefing for agents building Hunter in parallel.

## How it's built

Hunter is built under [doctrine](https://github.com/OmarAbdo/doctrine): every change is a small
item that starts with a failing test, passes `doctrine check`, and is merged by CI.
