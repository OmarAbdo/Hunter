# Briefing for agents working in parallel

You are one of several agents building Hunter at the same time, each in its own git worktree, on
one item, and you start without the context the others have. Read this before anything else; it
holds what the code and the docs don't show.

## Hunter in two lines

Hunter is Omar's own job-search pipeline. Its first part, discovery, reads job sources into a local
pool, and campaigns pick the jobs they want. Read `docs/discovery.md` and `docs/sources.md` first.

## How work is done here: doctrine

Hooks, git hooks and CI enforce doctrine's rules. A refusal says why and what to do instead: do
that, and never look for a way around it.

1. **Start the item** you were given, in your worktree, with exactly the scope you were given:
   `doctrine item start --kind <kind> --title "..." --scope <paths>`. Start an item in a command of
   its own.
2. **Test first:** write the failing test, run `doctrine test` (it records the red run), then write
   the code until `doctrine test` is green.
3. **`doctrine check`** must pass before you say anything works.
4. **Commit, finish and push:** `git add -A`, commit, run `doctrine item done`, commit again if it
   changed anything, then push your branch: `git push -u origin <your item branch>`, in a command of
   its own, naming the branch.
5. **Don't open a pull request, and never merge.** The coordinator reviews your branch and opens
   the pull request; CI's gates then merge it.

Doctrine's limits on every item and module:
- **Items:** 400 changed lines and 15 files at most.
- **Modules:** at most 12 import statements; at most 10 modules in a folder.
- **Functions:** at most 40 lines, complexity 7, nesting 2, 4 parameters.
- **Names:** at least 3 characters.
- **Never** write `noqa` or `type: ignore`.
- **Tests:** every domain or application module needs a unit test that imports it; every adapter
  module needs an integration test that imports it.
- **Coverage and mutation:** coverage of the changed lines is at least 85%, and mutation testing of
  domain and application code catches at least 70%.

## Your scope: your module, its tests, its saved responses

- **Stay inside your item's scope.** Doctrine refuses changes outside it.
- **Never edit the shared tables:**
  - `adapters/sources/feed_table.py`;
  - `adapters/sources/searches/search_table.py`;
  - the link patterns in `domain/discovery/boards.py`;
  - the source table in `docs/sources.md`.

  The coordinator wires new sources into them after your branch merges, so that their order (the
  link patterns' order matters) and their overview stay in one hand.
- **Test your module directly,** not through `discover`.

## Rules that matter more than they look

- **The repository is public.** Saved responses in `tests/fixtures/` hold nothing personal:
  - no names, mails or phone numbers of recruiters or people (remove them);
  - no keys or app ids (replace them with `app-id`, `the-key`, ...).

  Trim saved responses to a few jobs, one per line where it's JSON, so they don't eat the item's
  400 lines.
- **Keys:** keyed sources' keys are in `D:\1 Software\Projects\Hunter\var\accounts.toml` under
  `[keys.<source>]`.
  - Read them only for a few live checks.
  - Never print, log, commit or paste them.
  - Errors must not carry them either; use `adapters/sources/searches/keyed.py`.
- **Live requests:** only to your own source, a handful, one a second.
  - Never run `hunter discover` or `hunter boards probe`, and never touch `var/hunter.db`: the
    coordinator runs those.
  - Pacing doesn't reach across processes, and Workable already blocked Hunter for 21 hours once.
- **The bot rule** (`docs/sources.md`): where a site welcomes bots, Hunter names itself and
  follows its `robots.txt`. Where it turns bots away, tell the coordinator rather than deciding
  alone.
- **Match the code around you.** Look at a module of your kind first:
  - for search sources, `adapters/sources/searches/adzuna.py` (keyed) and `bundesagentur.py`;
  - for feeds, `adapters/sources/feeds/dvinci.py` (JSON) and `coveto.py` (RSS).

  Keep their docstring style: the module docstring says what the source is, what Hunter reads and
  what it can't. Use their test style too: tests against the local site from
  `tests/integration/sources/conftest.py`.

## Pitfalls already hit

- **Don't write files through the shell** (heredocs with Python or `sed`): backslashes come out
  mangled (`\n`, `\b`, `\u`). Use the editor tools for files.
- **Formatting:** run `ruff format --line-length 100` (via `.venv/Scripts/python -m ruff`) on new
  files before `doctrine check`.
- **Places:** `place_at` and `place_from_text` read places offline, and only know towns of 15,000
  people or more. Smaller towns keep only their country.
- **Times:** a time without a zone is taken as UTC.

## When you're done

Your final message goes to the coordinator, not to Omar. Give:
- your branch;
- what changed;
- the proof (tests, `doctrine check`, the live check with its numbers);
- what isn't verified;
- anything the coordinator must wire in: table entries, link patterns, docs rows, pace rules.
