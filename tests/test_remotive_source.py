"""remotive 源适配器测试。HTTP 全部 mock 掉，不碰真实 API。"""

import logging

import pytest
import requests

import findjobs.remotive_source as remotive_source
from findjobs.remotive_source import RemotiveSource, strip_html

RAW_KEYS = {
    'company_name', 'job_title', 'job_id', 'category', 'location', 'job_type',
    'special_program', 'job_description', 'job_requirements', 'apply_url', 'source_url',
}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(remotive_source.time, 'sleep', lambda *_: None)


def _job(**over):
    base = {
        'id': 123,
        'url': 'https://remotive.com/remote-jobs/backend-engineer-123',
        'title': 'Backend Engineer',
        'company': 'Acme Corp',
        'category': 'Software Development',
        'job_type': 'full_time',
        'publication_date': '2026-09-01T00:00:00',
        'candidate_required_location': 'Worldwide',
        'salary': '',
        'description': '<p>Build <strong>APIs</strong> &amp; pipelines</p>',
    }
    base.update(over)
    return base


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class StubSession:
    """按队列吐响应，顺带记下每次请求"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_fetch_canonicalizes_and_strips_html():
    session = StubSession([FakeResponse(payload={'jobs': [_job()]})])
    jobs = RemotiveSource(session=session).fetch()
    assert len(jobs) == 1
    job = jobs[0]
    assert RAW_KEYS <= set(job)
    assert job['company_name'] == 'Acme Corp'
    assert job['job_title'] == 'Backend Engineer'
    assert job['job_id'] == '123'
    assert job['location'] == 'Worldwide'
    assert job['job_description'] == 'Build APIs & pipelines'
    assert job['apply_url'] == 'https://remotive.com/remote-jobs/backend-engineer-123'
    # 归一 schema 之外的键保留下来给下游用
    assert job['publication_date'] == '2026-09-01T00:00:00'


def test_search_and_category_go_into_the_request():
    session = StubSession([FakeResponse(payload={'jobs': []})])
    RemotiveSource(search='llm', category='software-dev', limit=50, session=session).fetch()
    _, kwargs = session.calls[0]
    assert kwargs['params']['search'] == 'llm'
    assert kwargs['params']['category'] == 'software-dev'
    assert kwargs['params']['limit'] == 50


def test_request_failure_returns_empty_and_logs(caplog):
    session = StubSession([requests.ConnectionError('down')] * 3)
    with caplog.at_level(logging.WARNING):
        jobs = RemotiveSource(session=session).fetch()
    assert jobs == []
    assert any('remotive' in r.message for r in caplog.records)


def test_retry_exhaustion_on_5xx_then_success():
    session = StubSession([
        FakeResponse(status_code=500),
        FakeResponse(payload={'jobs': [_job(id=7, title='OK')]})])
    jobs = RemotiveSource(session=session).fetch()
    assert [j['job_id'] for j in jobs] == ['7']
    assert len(session.calls) == 2


def test_strip_html_handles_entities_and_whitespace():
    assert strip_html('<p>a &amp; <b>b</b><br>c</p>') == 'a & b c'
    assert strip_html('') == ''
