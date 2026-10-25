"""Doing several things at the same time that are mostly waiting for websites: reading sources,
probing for boards. Each site still takes its turns: the web client paces every host, across
threads. Results come back in the items' order, so what's stored never depends on which site
answered first; storing stays on the calling thread."""

from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait

from hunter.application.discover import Fetched, fetched
from hunter.application.ports import JobSource

WORKERS = 8  # things done at the same time
WAIT_STEP_SECONDS = 0.5
WAIT_STEPS = 7200  # an hour of steps: far longer than any one thing takes


def read_in_parallel(sources: Sequence[JobSource]) -> Iterator[tuple[JobSource, Fetched]]:
    return in_parallel(fetched, sources)


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


def waited[Result](future: Future[Result]) -> Result:
    """Waits in short steps, so Ctrl+C can still stop a run (on Windows a plain wait can't be).
    The steps are counted, not looped on until done, so the wait can never last forever."""
    for _ in range(WAIT_STEPS):
        if future.done():
            break
        wait([future], timeout=WAIT_STEP_SECONDS)
    return future.result()
