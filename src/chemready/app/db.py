"""SQLite database: the six PRD tables plus users and password resets.

The field_value table is the audit trail: every extracted value with its page,
quote, checks and who reviewed it. Plain SQL with the standard library keeps the
MVP simple; move to Postgres when a second facility goes live (PRD).
"""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS facility (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    solution_provider TEXT NOT NULL DEFAULT '',
    sds_max_age_years INTEGER NOT NULL DEFAULT 3 CHECK (sds_max_age_years BETWEEN 1 AND 10),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS app_user (
    id INTEGER PRIMARY KEY,
    facility_id INTEGER NOT NULL REFERENCES facility(id),
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL DEFAULT 'Chemical manager',
    password_hash TEXT NOT NULL,
    session_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS password_reset (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES app_user(id),
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    used_at TEXT
);

CREATE TABLE IF NOT EXISTS sds_document (
    id INTEGER PRIMARY KEY,
    facility_id INTEGER NOT NULL REFERENCES facility(id),
    file_name TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    pages INTEGER NOT NULL DEFAULT 0,
    is_private INTEGER NOT NULL DEFAULT 1,
    is_scanned INTEGER NOT NULL DEFAULT 0,
    missing_sections TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'extracting', 'in_review', 'approved', 'failed')),
    stage TEXT NOT NULL DEFAULT 'Queued',
    error TEXT,
    provider TEXT,
    model TEXT,
    prompt_version TEXT,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms REAL NOT NULL DEFAULT 0,
    uploaded_by INTEGER REFERENCES app_user(id),
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (facility_id, file_hash)
);

CREATE TABLE IF NOT EXISTS field_value (
    id INTEGER PRIMARY KEY,
    sds_id INTEGER NOT NULL REFERENCES sds_document(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    label TEXT NOT NULL,
    value TEXT,
    original_value TEXT,
    page INTEGER,
    quote TEXT,
    confidence REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK (status IN ('passed', 'needs_review', 'missing')),
    check_result TEXT NOT NULL DEFAULT '{}',
    reasons TEXT NOT NULL DEFAULT '[]',
    extra TEXT NOT NULL DEFAULT '{}',
    reviewed INTEGER NOT NULL DEFAULT 0,
    resolution TEXT CHECK (resolution IN ('approved', 'edited', 'missing')),
    reviewed_by TEXT,
    reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS chemical_product (
    id INTEGER PRIMARY KEY,
    facility_id INTEGER NOT NULL REFERENCES facility(id),
    sds_id INTEGER NOT NULL UNIQUE REFERENCES sds_document(id),
    product_name TEXT,
    supplier TEXT,
    revision_date TEXT,
    signal_word TEXT,
    ppe TEXT,
    storage TEXT,
    note TEXT NOT NULL DEFAULT '',
    approved_by TEXT NOT NULL,
    approved_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingredient (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES chemical_product(id) ON DELETE CASCADE,
    substance_name TEXT,
    cas_number TEXT,
    cas_valid INTEGER,
    percent_range TEXT
);

CREATE TABLE IF NOT EXISTS hazard (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES chemical_product(id) ON DELETE CASCADE,
    h_code TEXT,
    statement TEXT,
    pictogram TEXT
);

CREATE INDEX IF NOT EXISTS idx_document_facility ON sds_document(facility_id, status);
CREATE INDEX IF NOT EXISTS idx_field_sds ON field_value(sds_id);
CREATE INDEX IF NOT EXISTS idx_product_facility ON chemical_product(facility_id);
"""


def connect(path: Path) -> sqlite3.Connection:
    """Open the database, creating the folder and tables if needed."""
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.executescript(SCHEMA)
    return connection
