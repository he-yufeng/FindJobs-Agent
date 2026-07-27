"""The skill-label library ships with the repo; a fresh clone must parse it."""

import csv
from pathlib import Path

LABELS_CSV = Path(__file__).resolve().parent.parent / "all_labels.csv"


def test_labels_csv_is_tracked_and_parses():
    assert LABELS_CSV.exists(), (
        "all_labels.csv is missing; resume/job tagging has no label source"
    )
    with LABELS_CSV.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) > 4000
    assert {"level_3rd", "skill_type", "tags"} <= set(rows[0])
    assert all(row["tags"].strip() for row in rows[:100])
