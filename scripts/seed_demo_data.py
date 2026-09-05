"""Build a demo jobs.db from the bundled sample postings.

Demo mode (FINDJOBS_DEMO=1) calls seed_demo_data() on startup when jobs.db is
empty. It also works standalone from the repo root:

    python scripts/seed_demo_data.py [path/to/jobs.db]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import storage

SAMPLE_JOBS_FILE = ROOT / "data" / "sample_jobs.json"


def load_sample_jobs() -> list[dict]:
    return json.loads(SAMPLE_JOBS_FILE.read_text(encoding="utf-8"))


def seed_demo_data(db_path) -> int:
    """Upsert the bundled sample postings into db_path. Returns rows written."""
    return storage.upsert_jobs(db_path, load_sample_jobs())


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "jobs.db")
    print(f"Seeded {seed_demo_data(target)} sample jobs into {target}")
