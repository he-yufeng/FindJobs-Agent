"""Demo mode end to end: Flask test client, stub LLM, no network.

Every test here runs with FINDJOBS_DEMO=1 and a tripwire on requests.post,
so a regression that leaks a real API call fails loudly.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

import findjobs.api_server as api_server
import findjobs.storage as storage
from findjobs.demo_llm import DemoLLM
from scripts.seed_demo_data import load_sample_jobs, seed_demo_data

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_RESUME = ROOT / "data" / "sample_resume.pdf"


def _no_network(*args, **kwargs):
    raise AssertionError("demo mode must not call the network")


@pytest.fixture()
def demo_client(tmp_path, monkeypatch):
    monkeypatch.setenv("FINDJOBS_DEMO", "1")
    monkeypatch.setattr("requests.post", _no_network)
    monkeypatch.setattr("findjobs.api_server.ROOT_DIR", tmp_path)
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr("findjobs.api_server.UPLOAD_FOLDER", upload_dir)
    monkeypatch.setattr(api_server.resume_parser, "llm", DemoLLM())
    monkeypatch.setattr(api_server.interview_agent, "llm", DemoLLM())
    api_server.jobs_store.clear()
    api_server.app.config["TESTING"] = True
    with api_server.app.test_client() as client:
        yield client


def _upload_sample_resume(client):
    data = {"file": (io.BytesIO(SAMPLE_RESUME.read_bytes()), "sample_resume.pdf")}
    resp = client.post("/api/resume/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    return resp.get_json()


# ------------------------------------------------------------------
# seed script + sample data
# ------------------------------------------------------------------

def test_seed_script_writes_sample_jobs(tmp_path):
    sample = load_sample_jobs()
    assert len(sample) >= 50
    for row in sample:
        assert not (set(row) - set(storage.JOB_COLUMNS)), row["job_id"]
        assert row["job_title"] and row["company_name"] and row["skill_tags"]

    db = tmp_path / "jobs.db"
    assert seed_demo_data(db) == len(sample)
    assert storage.count_jobs(db) == len(sample)
    loaded = {j["job_id"] for j in storage.load_jobs(db)}
    assert loaded == {j["job_id"] for j in sample}


# ------------------------------------------------------------------
# demo mode through the API
# ------------------------------------------------------------------

def test_health_reports_demo_flag(demo_client):
    body = demo_client.get("/api/health").get_json()
    assert body["status"] == "ok"
    assert body["demo"] is True


def test_health_demo_flag_off_without_env(monkeypatch):
    monkeypatch.delenv("FINDJOBS_DEMO", raising=False)
    api_server.app.config["TESTING"] = True
    with api_server.app.test_client() as client:
        assert client.get("/api/health").get_json()["demo"] is False


def test_jobs_seeded_on_first_request(demo_client, tmp_path):
    resp = demo_client.get("/api/jobs")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data_source"] == "sqlite"
    assert body["total"] == len(load_sample_jobs()) >= 50
    assert storage.count_jobs(tmp_path / "jobs.db") == body["total"]

    job = body["jobs"][0]
    assert job["title"] and job["company"] and job["required_skills"]
    assert job["apply_url"].startswith("http")


def test_seed_is_idempotent(demo_client, tmp_path):
    first = demo_client.get("/api/jobs").get_json()["total"]
    second = demo_client.get("/api/jobs").get_json()["total"]
    assert first == second == storage.count_jobs(tmp_path / "jobs.db")


def test_resume_upload_with_bundled_sample_pdf(demo_client, tmp_path):
    body = _upload_sample_resume(demo_client)

    info = body["resume"]["extracted_info"]
    assert info["name"] == "Chen Xiaoyu"
    assert info["email"] == "xiaoyu.chen@example.com"
    assert [e["school"] for e in info["education"]] == [
        "The University of Hong Kong",
        "Sun Yat-sen University",
    ]
    assert {e["company"] for e in info["experience"]} == {"Moonshot AI", "Tencent"}

    skills = body["skills"]
    assert skills, "stub LLM should score the sample resume's skills"
    assert all(1 <= s["score"] <= 5 for s in skills)
    by_name = {s["skill_name"]: s["score"] for s in skills}
    assert by_name["Python"] >= 3

    persisted = storage.load_resume(tmp_path / "jobs.db", body["resume"]["id"])
    assert persisted is not None
    assert persisted["extracted_info"]["name"] == "Chen Xiaoyu"


def test_match_jobs_against_uploaded_resume(demo_client):
    resume_id = _upload_sample_resume(demo_client)["resume"]["id"]
    demo_client.get("/api/jobs")

    resp = demo_client.post("/api/jobs/match", json={"resume_id": resume_id})
    assert resp.status_code == 200
    matches = resp.get_json()["matches"]
    assert len(matches) == len(load_sample_jobs())

    counts = [len(m["matched_skills"]) for m in matches]
    assert counts == sorted(counts, reverse=True), "matches should stay sorted by matched skill count"
    assert matches[0]["match_score"] > 0
    assert matches[0]["matched_skills"]
    assert any(m["missing_skills"] for m in matches)


def test_interview_full_roundtrip(demo_client, tmp_path):
    resume_id = _upload_sample_resume(demo_client)["resume"]["id"]
    job = demo_client.get("/api/jobs").get_json()["jobs"][0]

    resp = demo_client.post(
        "/api/interview/start", json={"resume_id": resume_id, "job_id": job["id"]}
    )
    assert resp.status_code == 200
    start = resp.get_json()
    assert start["stage"] == "greeting"
    assert job["title"] in start["message"], "greeting should mention the target role"

    session_id = start["session_id"]
    answer = (
        "我在实习中负责过一个检索增强问答系统，从数据清洗、索引构建到线上部署都参与过。"
        "印象最深的是上线初期准确率不达标，我先从日志定位到召回阶段的文档切分策略不合理，"
        "把固定长度切分改成按语义段落切分，又加了基于 PyTorch 的双语重排序，"
        "最终内部评测集上的 top1 准确率从七成提升到九成以上，前后大概六周。"
    )

    resp = demo_client.post(
        f"/api/interview/{session_id}/message", json={"message": "面试官好，" + answer}
    )
    first = resp.get_json()
    assert first["stage"] == "qa"
    assert first["question"]

    last = None
    for _ in range(5):
        resp = demo_client.post(
            f"/api/interview/{session_id}/message", json={"message": answer}
        )
        assert resp.status_code == 200
        last = resp.get_json()

    assert last["stage"] == "summary"
    assert last["evaluation"]["score"] == 4
    assert last["final_feedback"]
    assert last["average_score"] == 4.0

    session = demo_client.get(f"/api/interview/{session_id}").get_json()
    assert len(session["messages"]) == 13  # greeting + 6 user + 6 assistant
    listed = demo_client.get("/api/interview").get_json()["sessions"]
    assert len(listed) == 1
    assert listed[0]["id"] == session_id

    persisted = storage.load_interview_session(tmp_path / "jobs.db", session_id)
    assert persisted is not None and persisted["status"] == "active"


def test_applications_roundtrip_on_seeded_job(demo_client):
    job = demo_client.get("/api/jobs").get_json()["jobs"][0]

    resp = demo_client.put(f"/api/applications/{job['id']}", json={"status": "bookmarked"})
    assert resp.status_code == 200

    body = demo_client.get("/api/applications").get_json()
    assert body["success"] is True
    assert len(body["applications"]) == 1
    item = body["applications"][0]
    assert item["job_id"] == job["id"]
    assert item["status"] == "bookmarked"
    assert item["job_title"] == job["title"]
    assert item["company_name"] == job["company"]

    demo_client.put(f"/api/applications/{job['id']}", json={"status": "applied", "note": "官网已投"})
    item = demo_client.get("/api/applications").get_json()["applications"][0]
    assert item["status"] == "applied"
    assert item["note"] == "官网已投"

    assert demo_client.delete(f"/api/applications/{job['id']}").get_json()["removed"] is True
    assert demo_client.get("/api/applications").get_json()["applications"] == []


# ------------------------------------------------------------------
# the stub itself
# ------------------------------------------------------------------

def test_enable_demo_mode_swaps_llm(monkeypatch):
    old_parser_llm = api_server.resume_parser.llm
    old_agent_llm = api_server.interview_agent.llm
    monkeypatch.setenv("FINDJOBS_DEMO", "1")
    try:
        assert api_server.enable_demo_mode() is True
        assert isinstance(api_server.resume_parser.llm, DemoLLM)
        assert isinstance(api_server.interview_agent.llm, DemoLLM)
    finally:
        api_server.resume_parser.llm = old_parser_llm
        api_server.interview_agent.llm = old_agent_llm

    monkeypatch.setenv("FINDJOBS_DEMO", "0")
    assert api_server.enable_demo_mode() is False


def test_stub_greeting_mentions_job_and_company():
    llm = DemoLLM()
    out = llm.chat(
        "You are a professional, friendly, and experienced AI interviewer.",
        'Target job information:\nJob title: 推荐算法工程师\nCompany: 字节跳动\n\n'
        '{"greeting": "...", "self_intro": "...", "stage": "greeting"}',
    )
    payload = json.loads(out)
    assert "字节跳动" in payload["greeting"]
    assert "推荐算法工程师" in payload["greeting"]
    assert payload["stage"] == "greeting"


def test_stub_evaluation_scales_with_answer_substance():
    llm = DemoLLM()

    def score(answer: str) -> int:
        out = llm.chat(
            "You are a professional, strict but fair AI interviewer.",
            f"Question:\n介绍一下你的项目\n\nCandidate's answer:\n{answer}\n\nPlease grade the answer (0-5).",
        )
        return json.loads(out)["score"]

    assert score("不知道") == 1
    assert score("我做过一个推荐系统项目，负责特征工程和模型训练。") == 2
    assert score("详细。" * 30) == 3
    assert score("详细。" * 100) == 5
