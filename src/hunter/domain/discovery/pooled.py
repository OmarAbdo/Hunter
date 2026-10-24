"""What adding a posting to the pool gives back: the job it shows, and whether it was new."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Pooled:
    job_id: int
    is_new: bool
