"""Reading several sources at the same time, since most of a discovery run is waiting for
websites. Each site still takes its turns: the web client paces every host, across threads. The
readings come back in the sources' order, so what's taken in never depends on which site answered
first."""

from collections.abc import Iterator, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait

from hunter.application.discover import Fetched, fetched
from hunter.application.ports import JobSource

READERS = 8  # sources read at the same time
WAIT_STEP_SECONDS = 0.5
WAIT_STEPS = 7200  # an hour of steps: far longer than any source takes


def read_in_parallel(sources: Sequence[JobSource]) -> Iterator[tuple[JobSource, Fetched]]:
    readers = ThreadPoolExecutor(max_workers=READERS, thread_name_prefix="source")
    readings = [(source, readers.submit(fetched, source)) for source in sources]
    try:
        for source, reading in readings:
            yield source, waited(reading)
    finally:
        readers.shutdown(wait=False, cancel_futures=True)


def waited(reading: Future[Fetched]) -> Fetched:
    """Waits in short steps, so Ctrl+C can still stop a run (on Windows a plain wait can't be).
    The steps are counted, not looped on until done, so the wait can never last forever."""
    for _ in range(WAIT_STEPS):
        if reading.done():
            break
        wait([reading], timeout=WAIT_STEP_SECONDS)
    return reading.result()
