"""pipeline step1 的 remotive 可选接线：默认不拉，开了才拉，失败不拖垮公司爬虫。"""

import json
import subprocess
from pathlib import Path

import findjobs.pipeline as pipeline
import findjobs.remotive_source as remotive_source


def _fake_run_factory(root: Path):
    def fake_run(cmd, **_kwargs):
        # 公司爬虫子进程照常产出一条
        (root / 'crawled_jobs_raw.json').write_text(
            json.dumps([{'company_name': '腾讯', 'job_id': 'TC_1'}], ensure_ascii=False),
            encoding='utf-8',
        )
        return subprocess.CompletedProcess(cmd, 0)

    return fake_run


class _FakeRemotive:
    """进程内的假 RemotiveSource，记录构造参数。"""

    seen = None

    def __init__(self, search='', category='', limit=200, **_kwargs):
        _FakeRemotive.seen = {'search': search, 'category': category, 'limit': limit}

    def fetch(self):
        return [
            {'company_name': 'Acme', 'job_id': 'RM_1'},
            {'company_name': '腾讯', 'job_id': 'TC_1'},  # 重复，应被去重
        ]


class _FailingRemotive:
    def __init__(self, **_kwargs):
        pass

    def fetch(self):
        raise RuntimeError('remotive down')


def test_remotive_off_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, 'ROOT_DIR', tmp_path)
    monkeypatch.setattr(pipeline.subprocess, 'run', _fake_run_factory(tmp_path))
    _FakeRemotive.seen = None
    monkeypatch.setattr(remotive_source, 'RemotiveSource', _FakeRemotive)

    result = pipeline.step1_crawl_jobs()

    assert result['success'] is True
    assert result['count'] == 1
    assert _FakeRemotive.seen is None  # remotive 源未被构造


def test_remotive_merged_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, 'ROOT_DIR', tmp_path)
    monkeypatch.setattr(pipeline.subprocess, 'run', _fake_run_factory(tmp_path))
    _FakeRemotive.seen = None
    monkeypatch.setattr(remotive_source, 'RemotiveSource', _FakeRemotive)

    result = pipeline.step1_crawl_jobs(
        remotive={'search': 'backend', 'category': 'software-dev', 'max_jobs': 50}
    )

    assert result['success'] is True
    assert result['count'] == 2
    jobs = json.loads((tmp_path / 'crawled_jobs_raw.json').read_text(encoding='utf-8'))
    ids = {(j['company_name'], j['job_id']) for j in jobs}
    assert ids == {('腾讯', 'TC_1'), ('Acme', 'RM_1')}
    assert _FakeRemotive.seen == {'search': 'backend', 'category': 'software-dev', 'limit': 50}


def test_remotive_failure_keeps_company_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, 'ROOT_DIR', tmp_path)
    monkeypatch.setattr(pipeline.subprocess, 'run', _fake_run_factory(tmp_path))
    monkeypatch.setattr(remotive_source, 'RemotiveSource', _FailingRemotive)

    result = pipeline.step1_crawl_jobs(remotive={'search': 'x'})

    assert result['success'] is True
    assert result['count'] == 1  # 公司爬虫结果不受影响
