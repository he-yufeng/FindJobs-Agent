"""Ashby 招聘板源适配器测试（fake session，不打外网）。"""

import json
from typing import Any

from findjobs.ashby_source import DEFAULT_COMPANIES, AshbyApiSource
from findjobs.job_source import AshbyJobSource


class _FakeResp:
    def __init__(self, status: int, payload: Any = None):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, routes: dict[str, _FakeResp]):
        self.routes = routes
        self.headers: dict = {}
        self.calls: list[str] = []

    def get(self, url: str, timeout: int = 20, **_kw) -> _FakeResp:
        self.calls.append(url)
        return self.routes.get(url, _FakeResp(500))


def _job_payload(job_id: str, title: str = "Engineer", listed: bool = True) -> dict:
    return {
        "id": job_id,
        "title": title,
        "department": "Engineering",
        "location": "San Francisco",
        "secondaryLocations": [{"location": "New York"}],
        "employmentType": "Full-time",
        "descriptionPlain": "Build things.\n\nOwn outcomes.",
        "jobUrl": f"https://jobs.ashbyhq.com/acme/{job_id}",
        "publishedAt": "2026-10-20T00:00:00Z",
        "isListed": listed,
    }


def _source_for(company: str, payload) -> AshbyApiSource:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{company}"
    session = _FakeSession({url: _FakeResp(200, {"jobs": payload})})
    return AshbyApiSource(companies=[company], session=session, request_interval=0)


def test_fetch_normalizes_to_canonical_keys():
    source = _source_for("acme", [_job_payload("id-1")])
    jobs = source.fetch()
    assert len(jobs) == 1
    job = jobs[0]
    assert job["company_name"] == "acme"
    assert job["job_title"] == "Engineer"
    assert job["job_id"] == "ASHBY_id-1"
    assert job["category"] == "Engineering"
    assert job["location"] == "San Francisco (+1)"
    assert job["job_type"] == "Full-time"
    assert "Build things." in job["job_description"]
    assert job["apply_url"].endswith("/id-1")


def test_unlisted_jobs_are_skipped():
    source = _source_for("acme", [_job_payload("id-1", listed=False), _job_payload("id-2")])
    jobs = source.fetch()
    assert [j["job_id"] for j in jobs] == ["ASHBY_id-2"]


def test_404_company_skips_without_error():
    url = "https://api.ashbyhq.com/posting-api/job-board/ghost"
    session = _FakeSession({url: _FakeResp(404)})
    source = AshbyApiSource(companies=["ghost"], session=session, request_interval=0)
    assert source.fetch() == []


def test_failing_company_does_not_take_down_the_run():
    good = "https://api.ashbyhq.com/posting-api/job-board/good"
    session = _FakeSession({good: _FakeResp(200, {"jobs": [_job_payload("id-9")]})})
    source = AshbyApiSource(companies=["bad", "good"], session=session, request_interval=0)
    jobs = source.fetch()
    assert [j["company_name"] for j in jobs] == ["good"]


def test_limit_caps_across_companies():
    routes = {
        f"https://api.ashbyhq.com/posting-api/job-board/c{i}": _FakeResp(
            200, {"jobs": [_job_payload(f"id-{i}-{n}") for n in range(3)]}
        )
        for i in range(3)
    }
    session = _FakeSession(routes)
    source = AshbyApiSource(companies=["c0", "c1", "c2"], limit=4, session=session, request_interval=0)
    assert len(source.fetch()) == 4


def test_registry_wrapper_passes_companies_string(monkeypatch):
    captured = {}

    class _Stub:
        def __init__(self, companies=None, limit=300):
            captured["companies"] = companies
            captured["limit"] = limit

        def fetch(self):
            return []

    monkeypatch.setattr("findjobs.ashby_source.AshbyApiSource", _Stub)
    source = AshbyJobSource({"companies": "openai, notion", "max_jobs": 50})
    source.fetch()
    assert captured["companies"] == ["openai", "notion"]
    assert captured["limit"] == 50


def test_default_companies_are_live_known_slugs():
    assert "openai" in DEFAULT_COMPANIES
    assert "scale" not in DEFAULT_COMPANIES  # 404 已证不在 Ashby
