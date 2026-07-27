"""SQLite-backed job store.

The API used to re-read a multi-MB CSV on every request. Enriched jobs now
live in a single SQLite file (``jobs.db``): the pipeline upserts into it after
each enrichment run, and the API reads from it directly. The CSV stays as a
human-readable export; on first run an existing ``jobs_enriched.csv`` is
migrated into the DB automatically.

The same file also backs the application board: each tracked job_id carries a
status (bookmarked / applied / replied / interview / offer / rejected), a free
note, and the last update time.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

JOB_COLUMNS = [
    "job_id",
    "job_title",
    "company_name",
    "job_description",
    "skill_tags",
    "location",
    "job_level1",
    "job_level2",
    "min_degree",
    "degree_priority",
    "major_requirement_text",
    "apply_url",
    "source_url",
    "category",
    "job_requirements",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    job_title TEXT,
    company_name TEXT,
    job_description TEXT,
    skill_tags TEXT,
    location TEXT,
    job_level1 TEXT,
    job_level2 TEXT,
    min_degree TEXT,
    degree_priority TEXT,
    major_requirement_text TEXT,
    apply_url TEXT,
    source_url TEXT,
    category TEXT,
    job_requirements TEXT
)
"""

_APPLICATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
)
"""

APPLICATION_STATUSES = (
    "bookmarked",
    "applied",
    "replied",
    "interview",
    "offer",
    "rejected",
)

_INSERT = (
    f"INSERT OR REPLACE INTO jobs ({', '.join(JOB_COLUMNS)}) "
    f"VALUES ({', '.join(['?'] * len(JOB_COLUMNS))})"
)


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path) -> None:
    with _connect(db_path) as conn:
        conn.execute(_SCHEMA)
        conn.execute(_APPLICATIONS_SCHEMA)


def count_jobs(db_path: str | Path) -> int:
    if not Path(db_path).exists():
        return 0
    try:
        with _connect(db_path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()
            return int(row[0]) if row else 0
    except sqlite3.Error:
        return 0


def upsert_jobs(db_path: str | Path, rows: list[dict]) -> int:
    """Insert or replace jobs keyed by job_id. Returns rows written."""
    if not rows:
        return 0
    init_db(db_path)
    values = [
        tuple(str(row.get(col, "") or "") for col in JOB_COLUMNS)
        for row in rows
    ]
    with _connect(db_path) as conn:
        conn.executemany(_INSERT, values)
    return len(values)


def load_jobs(db_path: str | Path) -> list[dict]:
    """Load all jobs as dicts keyed by the CSV column names."""
    if count_jobs(db_path) == 0:
        return []
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT {', '.join(JOB_COLUMNS)} FROM jobs"
        ).fetchall()
    return [dict(row) for row in rows]


def import_csv(db_path: str | Path, csv_path: str | Path) -> int:
    """Migrate an enriched CSV into the DB. Returns imported row count."""
    import pandas as pd

    df = pd.read_csv(csv_path).fillna("")
    rows = [row.to_dict() for _, row in df.iterrows()]
    return upsert_jobs(db_path, rows)


def set_application_status(
    db_path: str | Path, job_id: str, status: str, note: str = ""
) -> None:
    if status not in APPLICATION_STATUSES:
        raise ValueError(f"unknown application status: {status}")
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO applications (job_id, status, note, updated_at)"
            " VALUES (?, ?, ?, ?)",
            (job_id, status, note, datetime.now(timezone.utc).isoformat()),
        )


def load_applications(db_path: str | Path) -> list[dict]:
    """All tracked applications, newest update first."""
    if not Path(db_path).exists():
        return []
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT job_id, status, note, updated_at FROM applications"
            " ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def delete_application(db_path: str | Path, job_id: str) -> bool:
    if not Path(db_path).exists():
        return False
    init_db(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM applications WHERE job_id = ?", (job_id,))
    return cur.rowcount > 0
