"""Resumes and interview sessions must survive an API server restart.

The API used to keep both in module-level dicts, so every restart wiped
uploaded-resume metadata and mock-interview transcripts. They now live in
the same jobs.db SQLite file as jobs and applications.
"""

import importlib
import io
import sqlite3

import pytest

import storage


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "jobs.db"


def _resume(resume_id="r1"):
    return {
        "id": resume_id,
        "user_id": "default_user",
        "file_name": "ada.pdf",
        "file_url": f"/api/resume/file/{resume_id}",
        "extracted_info": {"name": "Ada", "education": [{"school": "HKU"}]},
        "upload_date": "2026-09-05T10:00:00",
        "status": "completed",
        "skills": [{"name": "Python", "score": 5}],
    }


def _session(session_id="s1", resume_id="r1"):
    return {
        "id": session_id,
        "resume_id": resume_id,
        "job_id": "job-1",
        "started_at": "2026-09-05T10:01:00",
        "finished_at": None,
        "status": "active",
        "stage": "greeting",
        "phase": "greeting",
        "qa_count": 0,
        "max_qa": 5,
        "messages": [],
    }


def _msg(msg_id, role, content, stage="qa", question=None, evaluation=None):
    return {
        "id": msg_id,
        "role": role,
        "content": content,
        "created_at": "2026-09-05T10:02:00",
        "question": question,
        "evaluation": evaluation,
        "stage": stage,
    }


# ---------------------------------------------------------------------------
# storage layer
# ---------------------------------------------------------------------------


def test_resume_roundtrip(db_path):
    storage.save_resume(db_path, _resume())

    loaded = storage.load_resume(db_path, "r1")

    assert loaded == _resume()


def test_load_resume_missing_db_or_id_is_none(db_path, tmp_path):
    assert storage.load_resume(tmp_path / "nope.db", "r1") is None
    storage.save_resume(db_path, _resume())
    assert storage.load_resume(db_path, "ghost") is None


def test_save_resume_replaces_on_reparse(db_path):
    storage.save_resume(db_path, _resume())
    updated = _resume()
    updated["status"] = "failed"
    storage.save_resume(db_path, updated)

    assert storage.load_resume(db_path, "r1")["status"] == "failed"


def test_interview_session_roundtrip_keeps_message_order(db_path):
    session = _session()
    storage.save_interview_session(db_path, session)
    storage.append_interview_message(db_path, "s1", _msg("m1", "assistant", "你好", stage="greeting"))
    storage.append_interview_message(db_path, "s1", _msg("m2", "user", "我叫 Ada"))
    storage.append_interview_message(
        db_path, "s1",
        _msg("m3", "assistant", "什么是 GIL？", question="什么是 GIL？", evaluation={"score": 4}),
    )
    session["stage"] = "qa"
    session["phase"] = "qa"
    session["qa_count"] = 1
    storage.save_interview_session(db_path, session)

    loaded = storage.load_interview_session(db_path, "s1")

    assert loaded["job_id"] == "job-1"
    assert loaded["qa_count"] == 1
    assert loaded["stage"] == "qa"
    assert [m["id"] for m in loaded["messages"]] == ["m1", "m2", "m3"]
    assert loaded["messages"][2]["evaluation"] == {"score": 4}
    assert loaded["messages"][0]["question"] is None


def test_load_interview_session_missing_is_none(db_path, tmp_path):
    assert storage.load_interview_session(tmp_path / "nope.db", "s1") is None
    assert storage.load_interview_session(db_path, "ghost") is None


def test_list_interview_sessions_newest_first(db_path):
    older = _session("s1")
    newer = _session("s2")
    newer["started_at"] = "2026-09-05T11:00:00"
    storage.save_interview_session(db_path, older)
    storage.save_interview_session(db_path, newer)
    storage.append_interview_message(db_path, "s1", _msg("m1", "assistant", "你好", stage="greeting"))

    sessions = storage.list_interview_sessions(db_path)

    assert [s["id"] for s in sessions] == ["s2", "s1"]
    assert sessions[1]["message_count"] == 1


def test_init_db_adds_new_tables_without_touching_existing_data(db_path):
    # a jobs.db written before resumes/interviews were persisted
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(storage._SCHEMA)
        conn.execute(storage._APPLICATIONS_SCHEMA)
        conn.execute(
            "INSERT INTO jobs (job_id, job_title) VALUES ('job-1', 'Title 1')"
        )
        conn.execute(
            "INSERT INTO applications (job_id, status, note, updated_at)"
            " VALUES ('job-1', 'applied', '', '2026-09-04T00:00:00')"
        )

    storage.init_db(db_path)

    # old rows survive, new tables work
    assert storage.load_job_ids(db_path) == {"job-1"}
    assert storage.load_applications(db_path)[0]["status"] == "applied"
    storage.save_resume(db_path, _resume())
    storage.save_interview_session(db_path, _session())
    assert storage.load_resume(db_path, "r1")["file_name"] == "ada.pdf"
    assert storage.load_interview_session(db_path, "s1")["status"] == "active"


# ---------------------------------------------------------------------------
# API layer: data must survive a full process restart against the same db
# ---------------------------------------------------------------------------


class _StubParser:
    def parse_resume(self, path):
        return {
            "extracted_info": {"name": "Ada"},
            "upload_date": "2026-09-05T10:00:00",
            "skills": [{"name": "Python", "score": 5}],
        }


class _StubAgent:
    def start_interview(self, resume_data, job_data):
        return {"greeting": "你好，Ada", "self_intro": "先做个自我介绍", "stage": "greeting"}

    def respond(self, user_message, conversation_history, resume_data, job_data, session_state):
        return {
            "message": "答得不错。下一题：什么是 GIL？",
            "phase": "qa",
            "qa_count": 1,
            "question": "什么是 GIL？",
            "evaluation": {"score": 4},
        }


def _wire(module, root):
    module.ROOT_DIR = root
    module.resume_parser = _StubParser()
    module.interview_agent = _StubAgent()
    module.app.config["TESTING"] = True
    return module.app.test_client()


def test_resume_and_interview_survive_restart(tmp_path):
    import api_server

    client = _wire(api_server, tmp_path)

    resp = client.post(
        "/api/resume/upload",
        data={"file": (io.BytesIO(b"%PDF-1.4 fake"), "ada.pdf")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    resume_id = resp.get_json()["resume"]["id"]

    resp = client.post("/api/interview/start", json={"resume_id": resume_id})
    assert resp.status_code == 200
    session_id = resp.get_json()["session_id"]

    resp = client.post(
        f"/api/interview/{session_id}/message",
        json={"message": "我叫 Ada，五年后端经验"},
    )
    assert resp.status_code == 200

    assert (tmp_path / "jobs.db").exists()

    # simulate a server restart: fresh module state, same db file
    reloaded = importlib.reload(api_server)
    client = _wire(reloaded, tmp_path)

    resp = client.get(f"/api/resume/{resume_id}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["resume"]["extracted_info"] == {"name": "Ada"}
    assert body["skills"] == [{"name": "Python", "score": 5}]

    resp = client.get(f"/api/interview/{session_id}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["session"]["resume_id"] == resume_id
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["assistant", "user", "assistant"]
    assert "GIL" in body["messages"][2]["content"]

    resp = client.get("/api/interview")
    assert resp.status_code == 200
    sessions = resp.get_json()["sessions"]
    assert [s["id"] for s in sessions] == [session_id]
    assert sessions[0]["message_count"] == 3

    # follow-up messages after the restart still land in the same session
    resp = client.post(
        f"/api/interview/{session_id}/message",
        json={"message": "GIL 是 CPython 的全局解释器锁"},
    )
    assert resp.status_code == 200
    body = client.get(f"/api/interview/{session_id}").get_json()
    assert len(body["messages"]) == 5


def test_unknown_resume_and_session_still_404(tmp_path):
    import api_server

    client = _wire(api_server, tmp_path)

    assert client.get("/api/resume/ghost").status_code == 404
    assert client.get("/api/interview/ghost").status_code == 404
    assert client.post(
        "/api/interview/ghost/message", json={"message": "hi"}
    ).status_code == 404
