"""Tests for the SQLite job store and the /api/jobs read path."""

import json
import sqlite3
import uuid

import pandas as pd
import pytest

import storage


def _row(i: int) -> dict:
    return {
        "job_id": f"job-{i}",
        "job_title": f"Title {i}",
        "company_name": "Acme",
        "job_description": "desc",
        "skill_tags": "Python %> 5, AI | SQL %> 4, AI",
        "location": "Shanghai",
        "job_level1": "tech",
        "job_level2": "backend",
        "min_degree": "bachelor",
        "degree_priority": "preferred",
        "major_requirement_text": "CS",
        "apply_url": "https://example.com/apply",
        "source_url": "https://example.com/post",
        "category": "engineering",
        "job_requirements": "3+ years",
    }


def test_upsert_and_load_roundtrip(tmp_path):
    db = tmp_path / "jobs.db"
    storage.upsert_jobs(db, [_row(1), _row(2)])

    assert storage.count_jobs(db) == 2
    rows = storage.load_jobs(db)
    by_id = {r["job_id"]: r for r in rows}
    assert by_id["job-1"]["job_title"] == "Title 1"
    assert by_id["job-2"]["skill_tags"] == "Python %> 5, AI | SQL %> 4, AI"


def test_upsert_replaces_existing_job(tmp_path):
    db = tmp_path / "jobs.db"
    storage.upsert_jobs(db, [_row(1)])
    updated = _row(1)
    updated["job_title"] = "Renamed"
    storage.upsert_jobs(db, [updated])

    assert storage.count_jobs(db) == 1
    assert storage.load_jobs(db)[0]["job_title"] == "Renamed"


def test_load_empty_db_returns_empty_list(tmp_path):
    db = tmp_path / "jobs.db"
    assert storage.count_jobs(db) == 0
    assert storage.load_jobs(db) == []


def test_import_csv_migrates_rows(tmp_path):
    csv_path = tmp_path / "jobs_enriched.csv"
    pd.DataFrame([_row(1), _row(2)]).to_csv(csv_path, index=False)
    db = tmp_path / "jobs.db"

    imported = storage.import_csv(db, csv_path)

    assert imported == 2
    assert storage.count_jobs(db) == 2
    assert storage.load_jobs(db)[0]["company_name"] == "Acme"


# ---------------------------------------------------------------------------
# /api/jobs read path
# ---------------------------------------------------------------------------


@pytest.fixture()
def api(tmp_path, monkeypatch):
    import api_server

    monkeypatch.setattr(api_server, "ROOT_DIR", tmp_path)
    api_server.app.config["TESTING"] = True
    return api_server.app.test_client()


def test_api_jobs_reads_from_sqlite(api, tmp_path):
    storage.upsert_jobs(tmp_path / "jobs.db", [_row(1)])

    resp = api.get("/api/jobs")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["data_source"] == "sqlite"
    assert len(payload["jobs"]) == 1
    assert payload["jobs"][0]["title"] == "Title 1"
    # 和 CSV 分支保持一致：required_skills 直接来自 parse_skill_tags，带熟练度分数
    assert payload["jobs"][0]["required_skills"] == ["Python %> 5", "SQL %> 4"]


def test_api_jobs_migrates_csv_on_first_run(api, tmp_path):
    pd.DataFrame([_row(1)]).to_csv(tmp_path / "jobs_enriched.csv", index=False)

    resp = api.get("/api/jobs")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["data_source"] == "sqlite"
    assert len(payload["jobs"]) == 1
    assert storage.count_jobs(tmp_path / "jobs.db") == 1
