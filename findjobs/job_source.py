#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可插拔岗位源（JobSource 接口）

爬虫、第三方招聘 API、本地 jobs.json 走同一入口：每个源实现
``name`` + ``fetch() -> list[dict]``，返回统一 schema 的岗位字典。
pipeline 只遍历注册表，用户换源/加源不改 pipeline 代码。

新增一个源就是新写一个类，例如：

    class MyApiSource:
        name = "my-api"
        def fetch(self) -> list[dict]:
            ...  # 拉数并归一到统一 schema

    from findjobs.job_source import register_source
    register_source(MyApiSource())
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent

# 岗位字典的统一 schema（各源归一到这些键；缺省键给空串，不下猜）
CANONICAL_KEYS = (
    'company_name', 'job_title', 'job_id', 'category', 'location', 'job_type',
    'special_program', 'job_description', 'job_requirements', 'apply_url',
    'source_url',
)


class JobSource(Protocol):
    """一个岗位来源：把"去拉岗位"变成统一 schema 的岗位列表。"""

    name: str

    def fetch(self) -> List[Dict[str, Any]]:
        """拉取并返回岗位字典列表；失败记日志并返回已抓到的部分，不抛给 pipeline。"""
        ...


def canonicalize(job: Dict[str, Any]) -> Dict[str, Any]:
    """把一条岗位记录归一到统一 schema：缺的键补空串，多余的键保留。"""
    return {key: job.get(key, '') or '' for key in CANONICAL_KEYS} | {
        k: v for k, v in job.items() if k not in CANONICAL_KEYS
    }


class JsonFileSource:
    """本地 JSON 岗位文件（demo 模式、离线回归、用户自有数据）。"""

    name = "json-file"

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def fetch(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            logger.error(f"json-file 源不存在: {self.path}")
            return []
        with open(self.path, 'r', encoding='utf-8') as f:
            jobs = json.load(f)
        logger.info(f"json-file 源: {self.path.name} 读出 {len(jobs)} 个岗位")
        return [canonicalize(job) for job in jobs]


class CompanyCrawlerSource:
    """公司定向爬虫组（job_crawler_v2 那一批 per-company 爬虫）。

    沿用子进程跑法：爬虫状态和信号处理与 `python -m findjobs.job_crawler_v2`
    完全一致，只是把它收进统一接口。
    """

    name = "company-crawlers"

    def __init__(self, companies: Optional[List[str]] = None, root: Optional[Path] = None):
        self.companies = companies
        self.root = Path(root) if root else ROOT_DIR

    def fetch(self) -> List[Dict[str, Any]]:
        raw_file = self.root / 'crawled_jobs_raw.json'
        cmd = [sys.executable, '-m', 'findjobs.job_crawler_v2', '-f', str(raw_file)]
        if self.companies:
            cmd.extend(['-c'] + self.companies)
        logger.info(f"company-crawlers 源: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=str(self.root))
        if result.returncode != 0:
            logger.warning("company-crawlers 源非零退出，读已有产物继续")
        if not raw_file.exists():
            logger.error("company-crawlers 源未生成输出文件")
            return []
        with open(raw_file, 'r', encoding='utf-8') as f:
            return [canonicalize(job) for job in json.load(f)]


class FreehireApiSource:
    """freehire.me 聚合 API（免 key 的 IT 职位聚合）。

    沿用子进程跑法，与 `python -m findjobs.freehire_source` 的参数面一致。
    """

    name = "freehire"

    def __init__(self, options: Optional[Dict[str, Any]] = None, root: Optional[Path] = None):
        self.options = dict(options or {})
        self.root = Path(root) if root else ROOT_DIR

    def fetch(self) -> List[Dict[str, Any]]:
        freehire_file = self.root / 'freehire_jobs_raw.json'
        options = self.options
        cmd = [
            sys.executable,
            '-m', 'findjobs.freehire_source',
            '-f', str(freehire_file),
            '-m', str(options.get('max_jobs') or 300),
        ]
        if options.get('query'):
            cmd += ['-q', options['query']]
        if options.get('skills'):
            cmd += ['--skills', options['skills']]
        if options.get('countries'):
            cmd += ['--countries', options['countries']]
        logger.info(f"freehire 源: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=str(self.root))
        if result.returncode != 0 or not freehire_file.exists():
            logger.warning("⚠️  freehire 源拉取失败，跳过该源继续")
            return []
        with open(freehire_file, 'r', encoding='utf-8') as f:
            return [canonicalize(job) for job in json.load(f)]


def dedupe_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按 公司+job_id（无 job_id 时 公司+标题+地点）去重，先到的赢。"""
    seen: set = set()
    unique: List[Dict[str, Any]] = []
    for job in jobs:
        key = (
            job.get('company_name', ''),
            job.get('job_id') or f"{job.get('job_title', '')}|{job.get('location', '')}",
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique


def default_sources(
    companies: Optional[List[str]] = None,
    freehire: Optional[Dict[str, Any]] = None,
    root: Optional[Path] = None,
) -> List[JobSource]:
    """默认注册表：公司爬虫组，配置了 freehire 时追加聚合源。"""
    sources: List[JobSource] = [CompanyCrawlerSource(companies, root=root)]
    if freehire:
        sources.append(FreehireApiSource(freehire, root=root))
    return sources


_registered: List[JobSource] = []


def register_source(source: JobSource) -> None:
    """往默认注册表尾部追加一个源（用户扩展位）。"""
    _registered.append(source)


def all_sources(
    companies: Optional[List[str]] = None,
    freehire: Optional[Dict[str, Any]] = None,
    root: Optional[Path] = None,
) -> List[JobSource]:
    """默认注册表 + 用户注册的所有源。"""
    return default_sources(companies=companies, freehire=freehire, root=root) + list(_registered)
