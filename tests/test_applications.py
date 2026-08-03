import json
import pytest

import storage
from api_server import app


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "jobs.db"


def test_set_and_load_applications_orders_newest_first(db_path):
    storage.set_application_status(db_path, "j1", "bookmarked")
    storage.set_application_status(db_path, "j2", "applied", note="referral")
    storage.set_application_status(db_path, "j1", "interview")

    items = storage.load_applications(db_path)

    assert [i["job_id"] for i in items] == ["j1", "j2"]
    assert items[0]["status"] == "interview"
    assert items[1]["note"] == "referral"


def test_unknown_status_rejected_without_writing(db_path):
    with pytest.raises(ValueError, match="unknown application status"):
        storage.set_application_status(db_path, "j1", "ghosted")
    assert storage.load_applications(db_path) == []


def test_delete_application_reports_whether_it_existed(db_path):
    assert storage.delete_application(db_path, "ghost") is False
    storage.set_application_status(db_path, "j1", "applied")
    assert storage.delete_application(db_path, "j1") is True
    assert storage.delete_application(db_path, "j1") is False


def test_load_applications_missing_db_is_empty(tmp_path):
    assert storage.load_applications(tmp_path / "nope.db") == []


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("api_server.ROOT_DIR", tmp_path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _seed_job(db_file, job_id="j1", title="编译器工程师", company="Moonshot"):
    row = {col: "" for col in storage.JOB_COLUMNS}
    row.update({"job_id": job_id, "job_title": title, "company_name": company})
    storage.upsert_jobs(db_file, [row])


def test_put_then_get_roundtrips_with_job_title(client, tmp_path):
    _seed_job(tmp_path / "jobs.db")

    resp = client.put("/api/applications/j1", json={"status": "applied", "note": "官网投的"})
    assert resp.status_code == 200

    resp = client.get("/api/applications")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert len(body["applications"]) == 1
    item = body["applications"][0]
    assert item["status"] == "applied"
    assert item["job_title"] == "编译器工程师"
    assert item["company_name"] == "Moonshot"
    assert set(body["statuses"]) == set(storage.APPLICATION_STATUSES)


def test_put_unknown_status_is_400_with_allowed_list(client):
    resp = client.put("/api/applications/j1", json={"status": "ghosted"})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert set(body["statuses"]) == set(storage.APPLICATION_STATUSES)


def test_delete_roundtrip(client, tmp_path):
    client.put("/api/applications/j1", json={"status": "bookmarked"})
    resp = client.delete("/api/applications/j1")
    assert resp.get_json()["removed"] is True
    resp = client.delete("/api/applications/j1")
    assert resp.get_json()["removed"] is False
