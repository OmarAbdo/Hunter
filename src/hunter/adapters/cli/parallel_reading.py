"""Doing several things at the same time that are mostly waiting for websites: reading sources,
probing for boards. Each site still takes its turns: the web client paces every host, across
threads. Results come back in the items' order, so what's stored never depends on which site
answered first; storing stays on the calling thread."""

import threading
from collections.abc import Callable, Iterable, Iterator, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait

from hunter.application.discover import Fetched, fetched
from hunter.application.ports import JobSource
from hunter.domain.discovery.posting import Posting

WORKERS = 8  # things done at the same time
WAIT_STEP_SECONDS = 0.5
WAIT_STEPS = 7200  # an hour of steps: far longer than any one thing takes


class RunStoppedError(Exception):
    """A run was stopped from Hunter's window."""


class RunControl:
    """Pausing and stopping a run from another thread. A source that hasn't started waits while
    the run is paused, and isn't read once it's stopped; a source being read is read to its end,
    so what's kept is always whole."""

    def __init__(self) -> None:
        self.going = threading.Event()
        self.going.set()
        self.stopped = False

    @property
    def paused(self) -> bool:
        return not self.going.is_set()

    def pause(self) -> None:
        self.going.clear()

    def resume(self) -> None:
        self.going.set()

    def stop(self) -> None:
        self.stopped = True
        self.going.set()

    def gated(self, sources: Sequence[JobSource]) -> list[JobSource]:
        return [Gated(source, self) for source in sources]

    def wait_turn(self) -> None:
        self.going.wait()
        if self.stopped:
            raise RunStoppedError


class Gated:
    """A source read only when its run may go on."""

    def __init__(self, source: JobSource, control: RunControl) -> None:
        self.source = source
        self.control = control
        self.name = source.name

    def fetch(self) -> Iterable[Posting]:
        self.control.wait_turn()
        return self.source.fetch()


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
