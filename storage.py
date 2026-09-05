"""SQLite-backed job store.

The API used to re-read a multi-MB CSV on every request. Enriched jobs now
live in a single SQLite file (``jobs.db``): the pipeline upserts into it after
each enrichment run, and the API reads from it directly. The CSV stays as a
human-readable export; on first run an existing ``jobs_enriched.csv`` is
migrated into the DB automatically.

The same file also backs the application board: each tracked job_id carries a
status (bookmarked / applied / replied / interview / offer / rejected), a free
note, and the last update time.

Uploaded resumes and mock-interview sessions live here too, so an API
restart no longer wipes them. Resume rows keep the parser output as JSON;
each interview session has its messages in a separate table, ordered by a
sequence number.
"""

from __future__ import annotations

import json
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

_RESUMES_SCHEMA = """
CREATE TABLE IF NOT EXISTS resumes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT '',
    file_name TEXT NOT NULL DEFAULT '',
    file_url TEXT NOT NULL DEFAULT '',
    upload_date TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    extracted_info TEXT NOT NULL DEFAULT '{}',
    skills TEXT NOT NULL DEFAULT '[]'
)
"""

_INTERVIEW_SESSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS interview_sessions (
    id TEXT PRIMARY KEY,
    resume_id TEXT,
    job_id TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    stage TEXT NOT NULL DEFAULT 'greeting',
    phase TEXT NOT NULL DEFAULT 'greeting',
    qa_count INTEGER NOT NULL DEFAULT 0,
    max_qa INTEGER NOT NULL DEFAULT 5
)
"""

_INTERVIEW_MESSAGES_SCHEMA = """
CREATE TABLE IF NOT EXISTS interview_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    question TEXT,
    evaluation TEXT,
    stage TEXT
)
"""

_INTERVIEW_MESSAGES_INDEX = """
CREATE INDEX IF NOT EXISTS idx_interview_messages_session
ON interview_messages (session_id, seq)
"""

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
        conn.execute(_RESUMES_SCHEMA)
        conn.execute(_INTERVIEW_SESSIONS_SCHEMA)
        conn.execute(_INTERVIEW_MESSAGES_SCHEMA)
        conn.execute(_INTERVIEW_MESSAGES_INDEX)


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


def load_job_ids(db_path: str | Path) -> set[str]:
    """Return the set of job_ids already stored (for incremental analysis)."""
    if not Path(db_path).exists():
        return set()
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT job_id FROM jobs").fetchall()
    return {str(row[0]) for row in rows}


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


def _dumps(value) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def save_resume(db_path: str | Path, resume: dict) -> None:
    """Insert or replace a parsed resume keyed by its id."""
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO resumes"
            " (id, user_id, file_name, file_url, upload_date, status,"
            "  extracted_info, skills)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                resume["id"],
                resume.get("user_id", ""),
                resume.get("file_name", ""),
                resume.get("file_url", ""),
                resume.get("upload_date", ""),
                resume.get("status", ""),
                _dumps(resume.get("extracted_info")),
                json.dumps(resume.get("skills") or [], ensure_ascii=False),
            ),
        )


def _resume_from_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "file_name": row["file_name"],
        "file_url": row["file_url"],
        "extracted_info": json.loads(row["extracted_info"] or "{}"),
        "upload_date": row["upload_date"],
        "status": row["status"],
        "skills": json.loads(row["skills"] or "[]"),
    }


def load_resume(db_path: str | Path, resume_id: str) -> dict | None:
    if not Path(db_path).exists():
        return None
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM resumes WHERE id = ?", (resume_id,)
        ).fetchone()
    return _resume_from_row(row) if row else None


def save_interview_session(db_path: str | Path, session: dict) -> None:
    """Insert or replace a session's metadata row (messages go separately)."""
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO interview_sessions"
            " (id, resume_id, job_id, started_at, finished_at, status,"
            "  stage, phase, qa_count, max_qa)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session["id"],
                session.get("resume_id"),
                session.get("job_id"),
                session.get("started_at", ""),
                session.get("finished_at"),
                session.get("status", "active"),
                session.get("stage", "greeting"),
                session.get("phase", "greeting"),
                int(session.get("qa_count", 0)),
                int(session.get("max_qa", 5)),
            ),
        )


def append_interview_message(db_path: str | Path, session_id: str, message: dict) -> None:
    """Append a message to a session; seq keeps the transcript order stable."""
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(seq) + 1, 0) FROM interview_messages"
            " WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        conn.execute(
            "INSERT INTO interview_messages"
            " (id, session_id, seq, role, content, created_at, question,"
            "  evaluation, stage)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                message["id"],
                session_id,
                int(row[0]),
                message.get("role", ""),
                message.get("content", ""),
                message.get("created_at", ""),
                message.get("question"),
                json.dumps(message["evaluation"], ensure_ascii=False)
                if message.get("evaluation") is not None
                else None,
                message.get("stage"),
            ),
        )


def _message_from_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "role": row["role"],
        "content": row["content"],
        "created_at": row["created_at"],
        "question": row["question"],
        "evaluation": json.loads(row["evaluation"]) if row["evaluation"] else None,
        "stage": row["stage"],
    }


def load_interview_session(db_path: str | Path, session_id: str) -> dict | None:
    """Session metadata plus its full transcript, in order. None if unknown."""
    if not Path(db_path).exists():
        return None
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM interview_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        messages = conn.execute(
            "SELECT * FROM interview_messages WHERE session_id = ? ORDER BY seq",
            (session_id,),
        ).fetchall()
    session = {
        "id": row["id"],
        "resume_id": row["resume_id"],
        "job_id": row["job_id"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "status": row["status"],
        "stage": row["stage"],
        "phase": row["phase"],
        "qa_count": row["qa_count"],
        "max_qa": row["max_qa"],
    }
    session["messages"] = [_message_from_row(m) for m in messages]
    return session


def list_interview_sessions(db_path: str | Path) -> list[dict]:
    """All sessions, newest first, with a message count instead of the transcript."""
    if not Path(db_path).exists():
        return []
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT s.*, COUNT(m.id) AS message_count"
            " FROM interview_sessions s"
            " LEFT JOIN interview_messages m ON m.session_id = s.id"
            " GROUP BY s.id"
            " ORDER BY s.started_at DESC"
        ).fetchall()
    return [
        {
            "id": row["id"],
            "resume_id": row["resume_id"],
            "job_id": row["job_id"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "status": row["status"],
            "stage": row["stage"],
            "qa_count": row["qa_count"],
            "message_count": row["message_count"],
        }
        for row in rows
    ]
