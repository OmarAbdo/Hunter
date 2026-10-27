"""Hunter's database: one SQLite file in var/ for the pool, the company registry, the campaign
matches and the discovery runs' reports. var/ is personal data and never committed
(docs/discovery.md)."""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    exact_key TEXT UNIQUE,
    fuzzy_key TEXT NOT NULL,
    posting TEXT NOT NULL,
    first_seen TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_by_fuzzy_key ON jobs (fuzzy_key);

CREATE TABLE IF NOT EXISTS sightings (
    job_id INTEGER NOT NULL REFERENCES jobs (id),
    source TEXT NOT NULL,
    native_id TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    PRIMARY KEY (source, native_id)
);

CREATE TABLE IF NOT EXISTS companies (
    key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    feeds TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS boards (
    board TEXT PRIMARY KEY,
    company_key TEXT NOT NULL REFERENCES companies (key)
);

CREATE TABLE IF NOT EXISTS websites (
    company_key TEXT PRIMARY KEY REFERENCES companies (key),
    website TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS probes (
    company_key TEXT PRIMARY KEY,
    probed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mail_marks (
    address TEXT NOT NULL,
    sender TEXT NOT NULL,
    validity INTEGER NOT NULL,
    last_uid INTEGER NOT NULL,
    PRIMARY KEY (address, sender)
);

CREATE TABLE IF NOT EXISTS matches (
    job_id INTEGER NOT NULL REFERENCES jobs (id),
    campaign_id TEXT NOT NULL,
    rejection TEXT,
    decided_at TEXT NOT NULL,
    PRIMARY KEY (job_id, campaign_id)
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    campaign_ids TEXT NOT NULL,
    linked_jobs INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS run_sources (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs (id),
    source TEXT NOT NULL,
    fetched INTEGER NOT NULL,
    new_jobs INTEGER NOT NULL,
    taken TEXT NOT NULL,
    error TEXT
);
CREATE INDEX IF NOT EXISTS run_sources_by_run ON run_sources (run_id);

CREATE TABLE IF NOT EXISTS holds (
    host TEXT PRIMARY KEY,
    until TEXT NOT NULL
);
"""


def open_database(path: Path) -> sqlite3.Connection:
    """In write-ahead-log mode, so the thousands of small commits of a discovery run don't each
    wait for the disk (one per posting took about a third of a second on Windows)."""
    database = sqlite3.connect(path)
    database.execute("PRAGMA journal_mode = WAL")
    database.execute("PRAGMA synchronous = NORMAL")
    database.executescript(SCHEMA)
    return database
