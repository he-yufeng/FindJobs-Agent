"""step1 incremental crawl: seen ledger, early stop, and new-only filtering."""

import json
from pathlib import Path

import findjobs.pipeline as pipeline
import findjobs.storage as storage
from findjobs import job_source
from findjobs.job_crawler_v2 import TencentCrawler


def _job(company: str, job_id: str) -> dict:
    return {
        "company_name": company,
        "job_title": f"title-{job_id}",
        "job_id": job_id,
        "category": "",
        "location": "SH",
        "job_type": "",
        "special_program": "",
        "job_description": "d",
        "job_requirements": "r",
        "apply_url": "",
        "source_url": "",
    }


# --- storage ledger ---------------------------------------------------------


def test_seen_ledger_roundtrip_and_refresh(tmp_path):
    db = tmp_path / "jobs.db"
    assert storage.load_seen_keys(db, "src") == set()
    storage.mark_seen(db, "src", ["Acme|1", "Acme|2"])
    assert storage.load_seen_keys(db, "src") == {"Acme|1", "Acme|2"}
    # a re-mark keeps the keys and only refreshes last_seen
    storage.mark_seen(db, "src", ["Acme|1"])
    assert storage.load_seen_keys(db, "src") == {"Acme|1", "Acme|2"}
    # ledgers are namespaced per source
    assert storage.load_seen_keys(db, "other") == set()


# --- job_key / dedupe identity ----------------------------------------------


def test_job_key_falls_back_to_title_location():
    assert job_source.job_key({"company_name": "Acme", "job_id": "42"}) == "Acme|42"
    assert job_source.job_key(
        {"company_name": "Acme", "job_id": "", "job_title": "Dev", "location": "SH"}
    ) == "Acme|Dev|SH"


def test_dedupe_uses_the_same_key_as_the_ledger():
    jobs = [_job("Acme", "1"), _job("Acme", "1"), _job("Acme", "2")]
    assert [job_source.job_key(j) for j in job_source.dedupe_jobs(jobs)] == [
        "Acme|1",
        "Acme|2",
    ]


# --- Tencent early stop -------------------------------------------------------


class _FakeResp:
    def __init__(self, posts, count):
        self._posts = posts
        self._count = count

    def json(self):
        return {"Data": {"Posts": self._posts, "Count": self._count}}


def _posts(ids):
    return [
        {"PostId": i, "RecruitPostName": f"t{i}", "LocationName": "", "CategoryName": "", "BGName": "", "Responsibility": "", "Requirement": ""}
        for i in ids
    ]


def test_tencent_stops_pagination_on_all_seen_page(monkeypatch):
    crawler = TencentCrawler()
    calls = []

    def fake_request(url, method="GET", **kwargs):
        page = kwargs["params"]["pageIndex"]
        calls.append(page)
        if page == 1:
            return _FakeResp(_posts(["a", "b"]), count=200)
        return _FakeResp(_posts(["c", "d"]), count=200)

    monkeypatch.setattr(crawler, "_request", fake_request)
    crawler.set_seen({"腾讯|TC_a", "腾讯|TC_b"})
    jobs = crawler.crawl()
    # page 1 was all-seen -> pagination stopped there, no new jobs kept
    assert calls == [1, 1]  # social + campus both stop after page 1
    assert jobs == []


def test_tencent_keeps_fetching_while_pages_have_new(monkeypatch):
    crawler = TencentCrawler()

    def fake_request(url, method="GET", **kwargs):
        page = kwargs["params"]["pageIndex"]
        if page == 1:
            return _FakeResp(_posts(["a", "b"]), count=200)
        return _FakeResp([], count=200)

    monkeypatch.setattr(crawler, "_request", fake_request)
    crawler.set_seen({"腾讯|TC_a"})  # only one of two seen: not an all-seen page
    jobs = crawler.crawl()
    assert {j["job_id"] for j in jobs} == {"TC_a", "TC_b"}


# --- pipeline step1 -----------------------------------------------------------


class _FakeSource:
    def __init__(self, name, jobs):
        self.name = name
        self._jobs = jobs
        self.seen_handoff = None

    def set_seen(self, keys):
        self.seen_handoff = set(keys)

    def fetch(self):
        return list(self._jobs)


def _run_step1(tmp_path, monkeypatch, sources):
    monkeypatch.setattr(pipeline, "ROOT_DIR", tmp_path)
    return pipeline.step1_crawl_jobs(sources=sources, incremental=True)


def test_step1_incremental_filters_seen_and_marks_fresh(tmp_path, monkeypatch):
    db = tmp_path / "jobs.db"
    storage.mark_seen(db, "fake", {"Acme|1"})
    source = _FakeSource("fake", [_job("Acme", "1"), _job("Acme", "2")])

    result = _run_step1(tmp_path, monkeypatch, [source])

    assert result["success"] and result["count"] == 1
    written = json.loads(Path(result["file"]).read_text(encoding="utf-8"))
    assert [j["job_id"] for j in written] == ["2"]
    # the source got the ledger handed off for early stopping
    assert source.seen_handoff == {"Acme|1"}
    # and the ledger now covers everything fetched
    assert storage.load_seen_keys(db, "fake") == {"Acme|1", "Acme|2"}


def test_step1_incremental_all_seen_is_success_with_zero_new(tmp_path, monkeypatch):
    db = tmp_path / "jobs.db"
    storage.mark_seen(db, "fake", {"Acme|1"})
    source = _FakeSource("fake", [_job("Acme", "1")])

    result = _run_step1(tmp_path, monkeypatch, [source])

    assert result["success"] and result["count"] == 0
    assert json.loads(Path(result["file"]).read_text(encoding="utf-8")) == []


def test_step1_full_mode_ignores_the_ledger(tmp_path, monkeypatch):
    db = tmp_path / "jobs.db"
    storage.mark_seen(db, "fake", {"Acme|1"})
    monkeypatch.setattr(pipeline, "ROOT_DIR", tmp_path)
    source = _FakeSource("fake", [_job("Acme", "1")])

    result = pipeline.step1_crawl_jobs(sources=[source], incremental=False)

    assert result["success"] and result["count"] == 1
    # and the handoff never happened in full mode
    assert source.seen_handoff is None
