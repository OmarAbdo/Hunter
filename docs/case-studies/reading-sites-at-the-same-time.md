# Case study: reading many sites at the same time, politely

How Hunter went from reading job sites one after another to reading several at once, without
asking any one site faster than it allows. The story runs from the first slow runs to a flaky
test, a wrong clock and a site that blocked Hunter for a day. It assumes no knowledge of Hunter.

## The setting

Hunter is a personal job-search tool. Its first part, **discovery**, collects job postings into one
local database, and each **campaign** (say, "full-time software jobs in Berlin") picks the jobs
that fit it. The postings come from **sources**:

- **Company boards.** Most companies publish jobs through an *applicant tracking system* (ATS)
  such as Greenhouse, Ashby or Personio. Each company has a **board** there, and the ATS offers a
  public, keyless address that returns the board's jobs, for example
  `boards-api.greenhouse.io/v1/boards/n26/jobs`. Hunter knows about 115 boards. One ATS serves
  all of its companies from **one host**: all 35 Greenhouse boards live on
  `boards-api.greenhouse.io`.
- **Searches** over many employers, such as the German federal employment agency's job search.
- **Alert mails** in an inbox (Indeed sends jobs by email).

A **discovery run** reads every source, adds what's new to the database, and lets every campaign
judge the new jobs. It runs from the command line and prints a line per source as it goes.

Two rules make this harder than it sounds:

1. **Be polite.** Every site gets a minimum gap between Hunter's requests (one second by
   default), and some sites get a daily cap. These are *per host*: the 35 Greenhouse boards
   share one budget, because they share one server.
2. **Stay predictable.** What ends up in the database must not depend on which site happened to
   answer first. The same inputs give the same pool.

## The problem: a run got slow

The first runs read sources one after another. Two things made that slow.

**Commits.** At first every posting was saved in its own database transaction. SQLite waits for
the disk on every commit, about a third of a second on Windows, so 15,000 postings took around
20 minutes. Switching SQLite to write-ahead logging (WAL), which makes small commits cheap, brought
a run down to about a minute (#19). That part had nothing to do with threads.

**Waiting for websites.** As the registry grew to about 105 boards, a run grew to **202 seconds**.
Almost all of that was waiting: for a server to answer, or for the one-second gap before the next
request to the same host. Hunter's own work (parsing JSON, matching titles) was a small part of it.
A program that mostly waits on the network is called **I/O-bound**. The cure for it is to do the
waiting for several things at once.

## Options considered

| Option | What it means here | Why not, or why |
|---|---|---|
| Keep it sequential | One source at a time | Simple, but a run grows linearly with every board added |
| `asyncio` | Rewrite every source as a coroutine with an async HTTP library | Every adapter changes, and a new dependency comes in (Python's built-in `urllib` isn't async). A large change for a program that does a few hundred requests per run |
| Processes (`multiprocessing`) | Several Python processes reading at once | Made for CPU-heavy work, which this isn't. Results would have to be copied between processes, and the database writes would still need one owner |
| **Threads** (`concurrent.futures.ThreadPoolExecutor`) | Several threads in one process, each reading one source | **Chosen.** Python releases its global lock (the GIL) while a thread waits on a socket, so threads really do wait in parallel. The sources stay plain synchronous code, nothing new is installed, and the change stays in one adapter |

A second choice was **where the politeness lives**. Throttling per source would be wrong: eight
threads reading eight Greenhouse boards would hit one host eight times at once. So the gap is kept
**per host**, in the one web client every source uses, and it holds across threads.

## The design

```
                 main thread                          worker threads (up to 8)
 sources ──► in_parallel(fetch, sources) ──submit──►  fetch(board A) ─┐
                 │                                     fetch(board B) ─┤─► WebClient ─► sites
                 │◄── results, in the sources' order ─ fetch(board C) ─┘   (one turn per host)
                 ▼
          take each result in: database, registry, campaign verdicts   (main thread only)
```

Three parts:

1. **`in_parallel`** (`src/hunter/adapters/cli/parallel_reading.py`) hands the sources to a pool of
   8 threads and gives the results back **in the order of the sources**, not the order they
   finished. That keeps rule 2: the taking-in is the same whichever site was fast today.
2. **Only the main thread touches the database.** Workers fetch and parse; the main thread stores.
   An SQLite connection shouldn't be shared between threads, and one writer means no write
   conflicts. (The inbox reader runs in a worker, so its small "mail already read" table opens a
   connection of its own for each use.)
3. **The web client takes turns per host** (`src/hunter/adapters/web_client.py`). Before each
   request, a thread takes that host's lock, waits until the host's gap has passed, notes the time
   and lets go.

The use case itself, the part that decides what a job is and which campaign takes it, knows
nothing of threads. It takes "a source and what it fetched", one pair at a time
(`take_each` in `src/hunter/application/discover.py`). Threads are a detail of the command line.

## How it works, in code

### Results in order

```python
def in_parallel[Item, Result](
    work: Callable[[Item], Result], items: Sequence[Item]
) -> Iterator[tuple[Item, Result]]:
    workers = ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="worker")
    futures = [(item, workers.submit(work, item)) for item in items]
    try:
        for item, future in futures:
            yield item, waited(future)
    finally:
        workers.shutdown(wait=False, cancel_futures=True)
```

Every source is submitted at once, and the pool runs 8 at a time. The generator then waits for
the futures **in submission order** and yields each result as soon as it, and every one before it,
is done. A slow first source holds back the printing of the others, but never their reading.
`shutdown(wait=False, cancel_futures=True)` in `finally` means that stopping early (an error, or
Ctrl+C) drops the queued work instead of waiting for it.

### Waiting that Ctrl+C can still stop

On Windows, a thread blocked in a plain `future.result()` doesn't see Ctrl+C until the wait ends,
and a hung site would make the program impossible to stop. So the wait happens in short steps:

```python
def waited[Result](future: Future[Result]) -> Result:
    for _ in range(WAIT_STEPS):          # 7,200 steps of half a second: an hour
        if future.done():
            break
        wait([future], timeout=WAIT_STEP_SECONDS)
    return future.result()
```

The first version was `while not future.done(): wait(...)`. It worked, but it hung Hunter's
**mutation testing**: that tool deliberately breaks the code in small ways (turning a condition
around, say) and checks that some test fails. One such mutant was a loop that never ends, and the
tool had no time limit per mutant. A **counted** loop can't run forever, whatever is changed in
it, so the steps are counted. The cost is a bound: after an hour, `future.result()` blocks as it
would have anyway.

### Taking turns per host

```python
def _wait_turn(self, host: str) -> None:
    with self._turn_of(host):                 # this host's lock
        now = self.clock()
        pause = self.pacing.wait(host, now)   # gap left, today's cap, any pause the site asked for
        if pause.total_seconds() > LONGEST_PAUSE_SECONDS:
            raise WebError(f"{host}: asked Hunter to wait until ...")
        if pause:
            self.sleep(pause.total_seconds())
        self.pacing.record(host, self.clock())

def _turn_of(self, host: str) -> threading.Lock:
    with self.turns_lock:                     # guards the table of locks itself
        return self.turns.setdefault(host, threading.Lock())
```

- **Two kinds of lock.** `turns_lock` guards only the table of per-host locks, so two threads
  asking for a new host's lock at the same moment get the same lock. The per-host lock then
  serialises the turns on that host. Threads reading different hosts never wait for each other.
- **The pace itself** is plain logic with no threads or clocks of its own
  (`src/hunter/domain/pacing.py`). It's told the time, says how long to wait and records each
  request. Keeping it pure is what makes it easy to test.
- **What's guaranteed is the gap between starts.** The lock is released as soon as the turn is
  recorded, before the request is sent. So turns on one host start at least one gap apart, but if
  a site takes longer than the gap to answer, two requests to it can be in flight at once. Sites
  count rate limits as requests per time window, so spacing the starts is what matters to them.

### The result

The same sources and about 15,000 postings took **85 seconds instead of 202** (#29), and about a
minute later on. Greenhouse alone still needs at least 35 seconds a run, since its 35 boards share
one host at one request a second. Reading in parallel shortens a run to roughly its busiest host.

## The flaky test (#43, #49, #51)

A test checks rule 1 across threads: three threads ask one host with a 0.3-second gap, and their
requests must be spaced that far apart. It took three tries to make that test measure the right
thing.

**First: when each answer came back.**

```python
def ask() -> None:
    client.get_json(f"{site}/jobs")
    asked.append(time.monotonic())        # when the answer came back
```

On a machine busy with a long probe run, it failed: two answers came back 0.23 seconds apart. The
pacing hadn't failed. A thread can be **scheduled late**: its request may wait to be sent after its
turn, and its answer may wait to be read. So answers can bunch up even when the turns were spaced
right. The test measured something the code never promised.

**Second: when each request reached the site (#43).** The local test server noted the arrival
time of every request. That was closer, but still not the promise:

- **After a restart, it failed every time.** Tracing showed the turns spaced exactly 0.3 seconds
  apart, yet the program's first request arrived up to 0.27 seconds late. The reason was Python's
  `urllib`, which looks up the system's proxy settings on first use, and on Windows that is slow.
  Sending one request before the threads start fixed that (#49).
- **During a full test run, it still failed now and then** (a 0.197-second gap). A thread can be
  delayed between its turn and the moment its request leaves, by however busy the machine is.

**Third: the turns themselves (#51).** Each turn reads the clock twice while it holds the host's
lock: once before its pause, once as the turn is recorded. The test gives the web client a clock
that notes every reading, and takes every second one as a turn:

```python
def clock() -> Moment:
    now = moment_now()
    readings.append(now.steady)
    return now
...
turns = readings[1::2]
assert min(gaps) >= 0.28  # Windows' monotonic clock ticks in steps of about 16 ms
```

That is exactly what the code promises, and a missing lock would still fail it: two threads would
then both take their turn after the same pause.

The lesson: with threads, observe the guarantee where it is made, not a side effect further down
the line that depends on scheduling.

## The clock (#49)

Looking into the test raised a second question: **which clock measures the gap?** The web client
used `datetime.now(UTC)`, the computer's wall clock. A wall clock can jump. Windows corrects it
from time to time against a time server, so a jump back by a minute would make the next wait a
minute longer, and a jump forward would shorten a gap.

Since #49, `Pacing` is given a `Moment`, which is now on two clocks:
- `wall`, the time of day, for the day of a daily cap and for a site's pause, since those name
  times of day;
- `steady`, from `time.monotonic()`, which only ever moves forward, for the gap since a host's
  last request.

## When pacing isn't enough: a site that asked for a day

Pacing keeps Hunter under the limits it knows of. Some sites have limits they don't publish. On
2026-10-25, probing guessed hundreds of possible board names on Workable at one request a second,
and Workable's public host began answering `429 Too Many Requests` with `Retry-After: 75335`,
about 21 hours.

The web client had capped any `Retry-After` at ten minutes and asked again, so it kept knocking.
Since #46:

- **The pause is read in full,** as seconds or as an HTTP date.
- **Up to ten minutes** is waited out within the run.
- **A longer pause holds the host:** `Pacing.hold(host, until)`. Every later request to that host,
  from any thread, fails at once without being sent, and the run reports those sources as
  unavailable until the time the site gave. The hold lives in the same per-host pace, so it
  reaches every thread at once.

## Where it stands, and what's next

- **Done:**
  - parallel reading (#29) and generic `in_parallel` (#33), used for probing too;
  - per-host turns and gaps;
  - holds for long pauses (#46);
  - a daily budget for Workable, and no more guessing on Workable when probing (#48);
  - gaps on the monotonic clock (#49);
  - the test that measures turns where they're taken (#51);
  - each source's published rate limits, in `docs/sources.md`.
- **Known limits:**
  - 8 workers is a first guess and hasn't been tuned;
  - holds and daily counts last one run; the next run starts counting again and asks a held site
    once more.
