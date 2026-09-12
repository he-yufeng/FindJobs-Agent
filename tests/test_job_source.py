"""JobSource 可插拔接口：统一 schema、注册表接线、用户自定义源零改动接入。"""

import json
from pathlib import Path

import findjobs.pipeline as pipeline
from findjobs.job_source import (
    JsonFileSource,
    all_sources,
    canonicalize,
    dedupe_jobs,
    register_source,
)


def test_canonicalize_fills_missing_keys_and_keeps_extras():
    job = canonicalize({'company_name': 'Acme', 'job_title': 'BE', 'extra_flag': True})

    for key in ('job_id', 'location', 'apply_url', 'source_url'):
        assert key in job and job[key] == ''
    assert job['extra_flag'] is True
    assert job['company_name'] == 'Acme'


def test_json_file_source_reads_and_normalizes(tmp_path):
    src_file = tmp_path / 'jobs.json'
    src_file.write_text(json.dumps([
        {'company_name': 'Acme', 'job_title': 'Backend'},
        {'company_name': 'Bee', 'job_title': 'FE', 'job_id': 'B1'},
    ], ensure_ascii=False), encoding='utf-8')

    jobs = JsonFileSource(src_file).fetch()

    assert len(jobs) == 2
    assert jobs[0]['company_name'] == 'Acme'
    assert jobs[0]['job_id'] == ''
    assert jobs[1]['job_id'] == 'B1'


def test_json_file_source_missing_file_returns_empty(tmp_path):
    assert JsonFileSource(tmp_path / 'nope.json').fetch() == []


def test_dedupe_jobs_by_company_and_id_or_fallback():
    jobs = [
        {'company_name': 'Acme', 'job_id': 'A1'},
        {'company_name': 'Acme', 'job_id': 'A1'},
        {'company_name': 'Acme', 'job_title': 'X', 'location': 'SH'},
        {'company_name': 'Acme', 'job_title': 'X', 'location': 'SH'},
        {'company_name': 'Acme', 'job_title': 'X', 'location': 'BJ'},
    ]

    assert len(dedupe_jobs(jobs)) == 3


def test_pipeline_uses_given_sources_without_any_crawler(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, 'ROOT_DIR', tmp_path)
    src_file = tmp_path / 'jobs.json'
    src_file.write_text(json.dumps([
        {'company_name': 'Acme', 'job_id': 'A1'},
        {'company_name': 'Acme', 'job_id': 'A1'},  # dup
        {'company_name': 'Bee', 'job_id': 'B1'},
    ], ensure_ascii=False), encoding='utf-8')

    called = []
    monkeypatch.setattr(pipeline.subprocess, 'run', lambda *a, **k: called.append(a))

    result = pipeline.step1_crawl_jobs(sources=[JsonFileSource(src_file)])

    assert result['success'] is True
    assert result['count'] == 2  # deduped
    assert called == []  # 文件源不触发任何爬虫子进程
    written = json.loads((tmp_path / 'crawled_jobs_raw.json').read_text(encoding='utf-8'))
    assert {j['company_name'] for j in written} == {'Acme', 'Bee'}


def test_register_source_plugs_a_custom_source(tmp_path, monkeypatch):
    """用户加一个源就是写一个类，不用碰 pipeline。"""
    monkeypatch.setattr(pipeline, 'ROOT_DIR', tmp_path)
    src_file = tmp_path / 'jobs.json'
    src_file.write_text(json.dumps([{'company_name': 'Acme', 'job_id': 'A1'}]), encoding='utf-8')

    class ToyApiSource:
        name = "toy-api"

        def fetch(self):
            return [{'company_name': 'ToyCo', 'job_id': 'T9'}]

    monkeypatch.setattr(pipeline.subprocess, 'run', lambda *a, **k: (_ for _ in ()).throw(RuntimeError("不该起爬虫")))
    from findjobs import job_source
    monkeypatch.setattr(job_source, '_registered', [ToyApiSource()])

    # 默认注册表（公司爬虫）+ 注册用户源；让"公司爬虫"也走文件，验证注册顺序
    result = pipeline.step1_crawl_jobs(
        sources=[JsonFileSource(src_file), *job_source._registered]
    )

    assert result['success'] is True
    assert result['count'] == 2
    written = json.loads((tmp_path / 'crawled_jobs_raw.json').read_text(encoding='utf-8'))
    assert {j['company_name'] for j in written} == {'Acme', 'ToyCo'}


def test_all_sources_appends_registered_after_defaults(monkeypatch):
    from findjobs import job_source

    monkeypatch.setattr(job_source, '_registered', [])
    defaults = all_sources(root=Path('/tmp'))
    assert [s.name for s in defaults] == ['company-crawlers']

    register_source(JsonFileSource('/tmp/x.json'))
    names = [s.name for s in all_sources(root=Path('/tmp'))]
    assert names == ['company-crawlers', 'json-file']
