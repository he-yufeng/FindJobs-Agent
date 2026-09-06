"""freehire 源适配器测试。HTTP 全部 mock 掉，不碰真实 API。"""

import json
import logging

import pytest
import requests

import findjobs.freehire_source as freehire_source
from findjobs.freehire_source import FreehireAPIError, FreehireCrawler

RAW_KEYS = {
    'company_name', 'job_title', 'job_id', 'category', 'location', 'job_type',
    'special_program', 'job_description', 'job_requirements', 'apply_url', 'source_url',
}


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    # 退避和限流等待都跳过，测试不等墙钟时间
    monkeypatch.setattr(freehire_source.time, 'sleep', lambda *_: None)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text=''):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = text or (json.dumps(payload) if payload is not None else '')

    def json(self):
        if self._payload is None:
            raise ValueError('no json')
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


def make_crawler(**kwargs) -> FreehireCrawler:
    kwargs.setdefault('request_interval', 0)
    return FreehireCrawler(**kwargs)


def fh_job(**overrides):
    job = {
        'public_slug': 'acme-backend-engineer-abc123',
        'title': 'Backend Engineer',
        'company': 'Acme',
        'company_slug': 'acme',
        'url': 'https://jobs.lever.co/acme/123',
        'location': 'Berlin, Germany',
        'source': 'lever',
        'description': '# Backend Engineer\n\nBuild APIs.\n\n## Requirements\n\n- Go\n- Kubernetes',
        'countries': ['de'],
        'cities': ['Berlin'],
        'work_mode': 'hybrid',
        'skills': ['go', 'kubernetes'],
        'is_tech': 'tech',
        'posted_at': '2026-08-20T10:00:00Z',
        'enrichment': {'category': 'engineering', 'employment_type': 'full_time', 'seniority': 'senior'},
    }
    job.update(overrides)
    return job


def envelope(jobs, total=None, **meta):
    m = {'total': total if total is not None else len(jobs), 'limit': len(jobs), 'offset': 0}
    m.update(meta)
    return {'data': jobs, 'meta': m}


def search_call(calls, index=-1):
    url, kwargs = calls[index]
    assert url.endswith('/agent/jobs/search')
    return kwargs['params']


def test_maps_full_result():
    crawler = make_crawler(query='backend')
    crawler.session = StubSession([FakeResponse(200, envelope([fh_job()]))])

    jobs = crawler.crawl()

    assert len(jobs) == 1
    job = jobs[0]
    assert set(job.keys()) == RAW_KEYS
    assert job['company_name'] == 'Acme'
    assert job['job_title'] == 'Backend Engineer'
    assert job['job_id'] == 'FH_acme-backend-engineer-abc123'
    # markdown JD 全文保留
    assert job['job_description'].startswith('# Backend Engineer')
    assert '## Requirements' in job['job_description']
    # apply 走公司官方 ATS 链接，source 留 freehire 页面
    assert job['apply_url'] == 'https://jobs.lever.co/acme/123'
    assert job['source_url'] == 'https://freehire.me/jobs/acme-backend-engineer-abc123'
    assert job['location'] == 'Berlin, Germany'
    assert job['category'] == 'engineering'
    assert job['job_type'] == 'full_time'

    params = search_call(crawler.session.calls)
    assert params['q'] == 'backend'
    assert params['description_format'] == 'markdown'
    assert params['is_tech'] == 'tech'
    assert params['limit'] == 100
    assert params['offset'] == 0


def test_missing_fields_tolerance():
    sparse = {'title': 'Mystery Job'}  # 只有必填三项里的一个
    crawler = make_crawler()
    crawler.session = StubSession([FakeResponse(200, envelope([sparse]))])

    jobs = crawler.crawl()

    assert len(jobs) == 1
    job = jobs[0]
    assert set(job.keys()) == RAW_KEYS
    assert job['job_title'] == 'Mystery Job'
    assert job['job_id']  # 没 slug 时基类用内容哈希兜底
    assert not job['job_id'].startswith('FH_')
    assert job['company_name'] == 'freehire'  # 公司缺失时退化为源名
    assert job['job_description'] == ''
    assert job['apply_url'] == ''
    assert job['source_url'] == ''


def test_location_falls_back_to_cities_countries():
    crawler = make_crawler()
    crawler.session = StubSession([
        FakeResponse(200, envelope([fh_job(location='', cities=['Berlin'], countries=['de'])]))
    ])

    job = crawler.crawl()[0]
    assert job['location'] == 'Berlin, de'


def test_pagination_stops_at_short_page():
    crawler = make_crawler(page_size=2)
    crawler.session = StubSession([
        FakeResponse(200, envelope([fh_job(), fh_job(public_slug='b')], total=3)),
        FakeResponse(200, envelope([fh_job(public_slug='c')], total=3)),
    ])

    jobs = crawler.crawl()

    assert len(jobs) == 3
    assert len(crawler.session.calls) == 2
    assert search_call(crawler.session.calls, 0)['offset'] == 0
    assert search_call(crawler.session.calls, 1)['offset'] == 2


def test_pagination_stops_at_total():
    crawler = make_crawler(page_size=2)
    crawler.session = StubSession([
        FakeResponse(200, envelope([fh_job(), fh_job(public_slug='b')], total=2)),
    ])

    jobs = crawler.crawl()

    assert len(jobs) == 2
    assert len(crawler.session.calls) == 1  # 满页但已到 total，不多发请求


def test_max_jobs_truncates():
    crawler = make_crawler(max_jobs=3, page_size=2)
    crawler.session = StubSession([
        FakeResponse(200, envelope([fh_job(), fh_job(public_slug='b')], total=10)),
        FakeResponse(200, envelope([fh_job(public_slug='c')], total=10)),
    ])

    jobs = crawler.crawl()

    assert len(jobs) == 3
    # 第二页只取剩余缺口：limit = min(page_size, 3-2) = 1
    assert search_call(crawler.session.calls, 1)['limit'] == 1


def test_empty_first_page_stops():
    crawler = make_crawler()
    crawler.session = StubSession([FakeResponse(200, envelope([], total=0))])

    assert crawler.crawl() == []
    assert len(crawler.session.calls) == 1


def test_facets_cached_and_skills_canonicalized():
    facets_payload = {'data': {'total': 100, 'facets': {'skills': {'python': 10, 'go': 5}}}}
    crawler = make_crawler(skills=['Python', 'nosuchskill'])
    crawler.session = StubSession([
        FakeResponse(200, facets_payload),      # facets
        FakeResponse(200, envelope([fh_job()])),  # search
    ])

    jobs = crawler.crawl()

    assert len(jobs) == 1
    assert crawler.session.calls[0][0].endswith('/jobs/facets')
    params = search_call(crawler.session.calls, 1)
    # 大小写对齐到 canonical slug；未知值原样透传
    assert params['skills'] == ['python', 'nosuchskill']

    # 再读 facets 走缓存，不发请求
    assert crawler.facet_values('skills') == {'python': 10, 'go': 5}
    assert len(crawler.session.calls) == 2

    # force_refresh 才重新拉
    crawler.session.responses.append(FakeResponse(200, facets_payload))
    crawler.get_facets(facets=['skills'], force_refresh=True)
    assert len(crawler.session.calls) == 3


def test_unknown_skill_logged(caplog):
    facets_payload = {'data': {'total': 1, 'facets': {'skills': {'python': 1}}}}
    crawler = make_crawler(skills=['cobol'])
    crawler.session = StubSession([
        FakeResponse(200, facets_payload),
        FakeResponse(200, envelope([])),
    ])

    with caplog.at_level(logging.WARNING):
        crawler.crawl()

    assert any('cobol' in r.message for r in caplog.records)


def test_facets_failure_passes_skills_through():
    crawler = make_crawler(skills=['python'])
    crawler.session = StubSession([
        FakeResponse(500, text='x'), FakeResponse(500, text='x'),
        FakeResponse(500, text='x'), FakeResponse(500, text='x'),  # facets 重试耗尽
        FakeResponse(200, envelope([fh_job()])),
    ])

    jobs = crawler.crawl()

    assert len(jobs) == 1
    assert search_call(crawler.session.calls)['skills'] == ['python']


def test_retry_on_server_error_then_success():
    crawler = make_crawler()
    crawler.session = StubSession([
        FakeResponse(500, text='boom'),
        FakeResponse(502, text='boom'),
        FakeResponse(200, envelope([fh_job()])),
    ])

    jobs = crawler.crawl()

    assert len(jobs) == 1
    assert len(crawler.session.calls) == 3


def test_gives_up_after_retries():
    crawler = make_crawler(max_retries=3)
    crawler.session = StubSession([FakeResponse(500, text='x')] * 4)

    jobs = crawler.crawl()

    assert jobs == []
    assert len(crawler.session.calls) == 4  # 1 + 3 次重试


def test_connection_error_retried():
    crawler = make_crawler()
    crawler.session = StubSession([
        requests.ConnectionError('nope'),
        FakeResponse(200, envelope([fh_job()])),
    ])

    assert len(crawler.crawl()) == 1


def test_429_retried_after_retry_after():
    crawler = make_crawler()
    crawler.session = StubSession([
        FakeResponse(429, payload={'error': 'slow down'}, headers={'Retry-After': '5'}),
        FakeResponse(200, envelope([fh_job()])),
    ])

    jobs = crawler.crawl()

    assert len(jobs) == 1
    assert len(crawler.session.calls) == 2


def test_client_error_not_retried():
    crawler = make_crawler()
    crawler.session = StubSession([FakeResponse(400, payload={'error': 'unknown facet'})])

    assert crawler.crawl() == []
    assert len(crawler.session.calls) == 1


def test_get_raises_after_exhausting_retries():
    crawler = make_crawler(max_retries=1)
    crawler.session = StubSession([FakeResponse(500, text='x')] * 2)

    with pytest.raises(FreehireAPIError):
        crawler._get('/jobs/facets')


def test_ignored_params_warned(caplog):
    payload = envelope([fh_job()], ignored_params=[{'param': 'country', 'did_you_mean': 'countries'}])
    crawler = make_crawler()
    crawler.session = StubSession([FakeResponse(200, payload)])

    with caplog.at_level(logging.WARNING):
        crawler.crawl()

    assert any('忽略了这些参数' in r.message and 'country' in r.message for r in caplog.records)
