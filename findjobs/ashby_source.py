#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ashby 招聘板岗位源适配器

Ashby 是海外 AI/科技公司常用的招聘系统（OpenAI、Perplexity、Notion、
Linear、Ramp 等都在用）。它的 posting API 免 key、单次调用返回该公司
全部公开岗位（含完整 JD 纯文本），不用再抓详情页：
GET https://api.ashbyhq.com/posting-api/job-board/{company}

与公司爬虫组互补：那批是国内大厂，这里是海外 AI 公司，同样归一到
CANONICAL_KEYS，下游分析/匹配零改动。
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

import requests

from .job_source import canonicalize

logger = logging.getLogger(__name__)

ASHBY_API_TEMPLATE = 'https://api.ashbyhq.com/posting-api/job-board/{company}'

# Ashby 侧没有强制 UA 要求，自报家门方便对方联系，与 remotive 同一姿态
ASHBY_UA = 'FindJobs-Agent/ashby-source (+https://github.com/he-yufeng/FindJobs-Agent)'

# 默认公司集：已核在 Ashby 上的海外 AI/科技公司（scale 等不在，404 已证）
DEFAULT_COMPANIES = ('openai', 'perplexity', 'notion', 'linear', 'ramp')

_WS_RE = re.compile(r'\s+')


class AshbyApiSource:
    """Ashby 招聘板源（免 key 公开 API，一公司一调用全量返回）。"""

    name = "ashby"

    def __init__(
        self,
        companies: Optional[List[str]] = None,
        limit: int = 300,
        timeout: int = 20,
        max_retries: int = 3,
        request_interval: float = 1.0,
        session: Optional[requests.Session] = None,
    ):
        self.companies = list(companies) if companies else list(DEFAULT_COMPANIES)
        self.limit = limit
        self.timeout = timeout
        self.max_retries = max_retries
        self.request_interval = request_interval
        self.session = session or requests.Session()
        self.session.headers.update({'User-Agent': ASHBY_UA})

    def _fetch_company(self, company: str) -> List[Dict[str, Any]]:
        url = ASHBY_API_TEMPLATE.format(company=company)
        payload: Optional[Dict[str, Any]] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code == 404:
                    logger.warning(f"ashby: {company} 不在 Ashby 上（404），跳过")
                    return []
                if resp.status_code == 429 or resp.status_code >= 500:
                    logger.warning(
                        f"ashby {company} {resp.status_code}，第 {attempt}/{self.max_retries} 次重试"
                    )
                    time.sleep(self.request_interval * attempt)
                    continue
                if resp.status_code != 200:
                    logger.error(f"ashby {company} 返回 {resp.status_code}，不重试，跳过")
                    return []
                payload = resp.json()
                break
            except requests.RequestException as exc:
                logger.warning(f"ashby {company} 请求异常 {exc}，第 {attempt}/{self.max_retries} 次重试")
                if attempt < self.max_retries:
                    time.sleep(self.request_interval * attempt)
        if payload is None:
            logger.error(f"ashby {company} 重试耗尽，跳过")
            return []

        jobs: List[Dict[str, Any]] = []
        for raw in payload.get('jobs', []):
            if not raw.get('isListed', True):
                continue
            location = raw.get('location') or ''
            secondary = raw.get('secondaryLocations') or []
            if secondary:
                extra = [loc.get('location', '') for loc in secondary if isinstance(loc, dict)]
                extra = [e for e in extra if e]
                if extra:
                    location = f"{location} (+{len(extra)})" if location else f"(+{len(extra)} 地)"
            jobs.append(canonicalize({
                'company_name': company,
                'job_title': raw.get('title', ''),
                'job_id': f"ASHBY_{raw.get('id', '')}",
                'category': raw.get('department', '') or raw.get('team', ''),
                'location': location,
                'job_type': raw.get('employmentType', ''),
                'job_description': _WS_RE.sub(' ', raw.get('descriptionPlain', '')).strip(),
                'job_requirements': '',
                'apply_url': raw.get('jobUrl', ''),
                'source_url': url,
                'publication_date': raw.get('publishedAt', ''),
            }))
        return jobs

    def fetch(self) -> List[Dict[str, Any]]:
        jobs: List[Dict[str, Any]] = []
        for company in self.companies:
            jobs.extend(self._fetch_company(company))
            if len(jobs) >= self.limit:
                break
            time.sleep(self.request_interval)
        jobs = jobs[: self.limit]
        logger.info(f"ashby 源: {len(jobs)} 个岗位（{len(self.companies)} 家公司）")
        return jobs
