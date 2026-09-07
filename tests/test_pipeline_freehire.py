"""pipeline step1 的 freehire 可选接线：默认不拉，开了才拉，合并按 公司+job_id 去重。"""

import json
import subprocess
from pathlib import Path

import findjobs.pipeline as pipeline


def _script_name(cmd: list) -> str:
    """Resolve the invoked script from a subprocess cmd.

    Steps call package modules as ``python -m findjobs.x``, so the identity
    sits in cmd[2]; keep the old ``python path/to/x.py`` shape working too.
    """
    if len(cmd) > 2 and cmd[1] == '-m':
        return cmd[2].split('.')[-1] + '.py'
    return Path(cmd[1]).name


def _fake_run_factory(root: Path, calls: list):
    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        script = _script_name(cmd)
        if script == 'job_crawler_v2.py':
            (root / 'crawled_jobs_raw.json').write_text(
                json.dumps([{'company_name': '腾讯', 'job_id': 'TC_1'}], ensure_ascii=False),
                encoding='utf-8',
            )
        elif script == 'freehire_source.py':
            out = Path(cmd[cmd.index('-f') + 1])
            out.write_text(
                json.dumps([
                    {'company_name': 'Acme', 'job_id': 'FH_x'},
                    {'company_name': '腾讯', 'job_id': 'TC_1'},  # 重复，应被去重
                ], ensure_ascii=False),
                encoding='utf-8',
            )
        return subprocess.CompletedProcess(cmd, 0)

    return fake_run


def test_freehire_off_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, 'ROOT_DIR', tmp_path)
    calls = []
    monkeypatch.setattr(pipeline.subprocess, 'run', _fake_run_factory(tmp_path, calls))

    result = pipeline.step1_crawl_jobs()

    assert result['success'] is True
    assert result['count'] == 1
    assert len(calls) == 1  # 只有公司爬虫，没有 freehire 子进程


def test_freehire_merged_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, 'ROOT_DIR', tmp_path)
    calls = []
    monkeypatch.setattr(pipeline.subprocess, 'run', _fake_run_factory(tmp_path, calls))

    result = pipeline.step1_crawl_jobs(freehire={'query': 'backend', 'max_jobs': 100})

    assert result['success'] is True
    assert result['count'] == 2
    jobs = json.loads((tmp_path / 'crawled_jobs_raw.json').read_text(encoding='utf-8'))
    ids = {(j['company_name'], j['job_id']) for j in jobs}
    assert ids == {('腾讯', 'TC_1'), ('Acme', 'FH_x')}

    fh_cmd = calls[1]
    assert _script_name(fh_cmd) == 'freehire_source.py'
    assert '-q' in fh_cmd and 'backend' in fh_cmd
    assert '-m' in fh_cmd and '100' in fh_cmd


def test_freehire_failure_keeps_company_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, 'ROOT_DIR', tmp_path)

    def fake_run(cmd, **_kwargs):
        script = _script_name(cmd)
        if script == 'job_crawler_v2.py':
            (tmp_path / 'crawled_jobs_raw.json').write_text(
                json.dumps([{'company_name': '腾讯', 'job_id': 'TC_1'}], ensure_ascii=False),
                encoding='utf-8',
            )
            return subprocess.CompletedProcess(cmd, 0)
        return subprocess.CompletedProcess(cmd, 1)  # freehire 挂了

    monkeypatch.setattr(pipeline.subprocess, 'run', fake_run)

    result = pipeline.step1_crawl_jobs(freehire={'query': 'x'})

    assert result['success'] is True
    assert result['count'] == 1  # 公司爬虫结果不受影响
