"""step2 incremental analysis: only new job_ids reach the LLM subprocess."""

import json
import subprocess
from pathlib import Path

import pandas as pd

import pipeline
import storage


def _write_raw(root: Path, ids: list[str]) -> None:
    jobs = [{"job_id": i, "job_title": f"job-{i}", "job_description": "d"} for i in ids]
    (root / "crawled_jobs_raw.json").write_text(
        json.dumps(jobs, ensure_ascii=False), encoding="utf-8"
    )


def _fake_run_factory(captured: dict, root: Path):
    def fake_run(cmd, **_kwargs):
        jobs_file = Path(cmd[cmd.index("--jobs-file") + 1])
        out_file = Path(cmd[cmd.index("--output-file") + 1])
        input_jobs = json.loads(jobs_file.read_text())
        captured["input_ids"] = [j["job_id"] for j in input_jobs]
        # the real job_agent analyzes the input rows; we just tag them through
        df = pd.DataFrame(input_jobs)
        df["skill_tags"] = "python"
        df.to_csv(out_file, index=False)
        return subprocess.CompletedProcess(cmd, 0)

    return fake_run


def _setup(tmp_path, monkeypatch):
    root = tmp_path
    monkeypatch.setattr(pipeline, "ROOT_DIR", root)
    return root


def test_incremental_analysis_only_sends_new_jobs(tmp_path, monkeypatch):
    root = _setup(tmp_path, monkeypatch)
    _write_raw(root, ["a", "b"])
    storage.upsert_jobs(root / "jobs.db", [{"job_id": "a", "job_title": "job-a"}])

    captured = {}
    monkeypatch.setattr(pipeline.subprocess, "run", _fake_run_factory(captured, root))

    result = pipeline.step2_analyze_with_llm()

    assert result["success"] is True
    assert captured["input_ids"] == ["b"]  # only the new one reached the LLM
    df = pd.read_csv(root / "jobs_enriched.csv")
    assert set(df["job_id"].astype(str)) == {"a", "b"}  # full set on disk


def test_no_new_jobs_skips_the_subprocess(tmp_path, monkeypatch):
    root = _setup(tmp_path, monkeypatch)
    _write_raw(root, ["a"])
    storage.upsert_jobs(root / "jobs.db", [{"job_id": "a", "job_title": "job-a"}])

    called = []
    monkeypatch.setattr(pipeline.subprocess, "run", lambda *a, **k: called.append(a))

    result = pipeline.step2_analyze_with_llm()

    assert result["success"] is True
    assert result["count"] == 0
    assert called == []


def test_reanalyze_all_sends_everything(tmp_path, monkeypatch):
    root = _setup(tmp_path, monkeypatch)
    _write_raw(root, ["a", "b"])
    storage.upsert_jobs(root / "jobs.db", [{"job_id": "a", "job_title": "job-a"}])

    captured = {}
    monkeypatch.setattr(pipeline.subprocess, "run", _fake_run_factory(captured, root))

    pipeline.step2_analyze_with_llm(reanalyze_all=True)

    assert captured["input_ids"] == ["a", "b"]
