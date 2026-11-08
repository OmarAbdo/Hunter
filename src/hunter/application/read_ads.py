"""Reading ads: a job a campaign took without its whole ad is read again, from the source that
showed it, where Hunter has a reader for that source. The ad is kept with the job. A job its source
no longer has is marked gone and isn't asked for again; one that couldn't be read this time is left
for the next run."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime

from hunter.application.ports import AdReader, AdStore, SourceUnavailableError
from hunter.domain.discovery.posting import Posting


def read_ads(
    store: AdStore, readers: Mapping[str, AdReader], now: datetime
) -> dict[str, Counter[str]]:
    """Each source's jobs, counted as read, gone or failed."""
    outcomes: dict[str, Counter[str]] = {}
    for job_id, posting in store.wanting():
        reader = readers.get(posting.source.source)
        if reader is not None:
            outcome = read_one(store, reader, (job_id, posting), now)
            outcomes.setdefault(posting.source.source, Counter()).update((outcome,))
    return outcomes


def read_one(store: AdStore, reader: AdReader, job: tuple[int, Posting], now: datetime) -> str:
    job_id, posting = job
    try:
        text = reader.read(posting)
    except SourceUnavailableError as error:
        if not error.gone:
            return "failed"
        store.mark_gone(job_id, now)
        return "gone"
    if not text.strip():
        return "failed"
    store.keep_ad(job_id, replace(posting, description=text), now)
    return "read"
