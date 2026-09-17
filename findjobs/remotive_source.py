#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remotive 远程岗位源适配器

Remotive 是老牌远程职位站，公开 API 免 key、调用合法稳定：
GET https://remotive.com/api/remote-jobs，返回 {"jobs": [...]}。
每条记录自带公司/标题/地点/类别/完整 JD(HTML) 和官方申请链接，
不用再抓详情页。文档: https://remotive.com/api/documentation
"""

from __future__ import annotations

import html as html_module
import logging
import re
import time
from typing import Any, Dict, List, Optional

import requests

from .job_source import canonicalize

logger = logging.getLogger(__name__)

REMOTIVE_API_URL = 'https://remotive.com/api/remote-jobs'

# Remotive 侧约定调用方自报家门，429 之前他们好先打招呼
REMOTIVE_UA = 'FindJobs-Agent/remotive-source (+https://github.com/he-yufeng/FindJobs-Agent)'

_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'\s+')


def strip_html(text: str) -> str:
    """JD 的 HTML 转纯文本：去标签、反转义实体、压空白，给 LLM 吃干净的。"""
    return _WS_RE.sub(' ', html_module.unescape(_TAG_RE.sub(' ', text or ''))).strip()


class RemotiveSource:
    """Remotive 远程岗位源（免 key 的公开 API）。

    与 freehire 互补：freehire 偏 IT 聚合，Remotive 偏全品类远程岗。
    """

    name = "remotive"

    def __init__(
        self,
        search: str = '',
        category: str = '',
        limit: int = 200,
        timeout: int = 20,
        max_retries: int = 3,
        request_interval: float = 1.0,
        session: Optional[requests.Session] = None,
    ):
        self.search = search
        self.category = category
        self.limit = limit
        self.timeout = timeout
        self.max_retries = max_retries
        self.request_interval = request_interval
        self.session = session or requests.Session()
        self.session.headers.update({'User-Agent': REMOTIVE_UA})

    def fetch(self) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {'limit': self.limit}
        if self.search:
            params['search'] = self.search
        if self.category:
            params['category'] = self.category

        payload: Optional[Dict[str, Any]] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(REMOTIVE_API_URL, params=params, timeout=self.timeout)
                if resp.status_code == 429 or resp.status_code >= 500:
                    logger.warning(
                        f"remotive {resp.status_code}，第 {attempt}/{self.max_retries} 次重试"
                    )
                    time.sleep(self.request_interval * attempt)
                    continue
                if resp.status_code != 200:
                    logger.error(f"remotive 返回 {resp.status_code}，不重试，跳过该源")
                    return []
                payload = resp.json()
                break
            except requests.RequestException as exc:
                logger.warning(f"remotive 请求异常 {exc}，第 {attempt}/{self.max_retries} 次重试")
                if attempt < self.max_retries:
                    time.sleep(self.request_interval * attempt)
        if payload is None:
            logger.error("remotive 重试耗尽，跳过该源继续")
            return []

        jobs: List[Dict[str, Any]] = []
        for raw in payload.get('jobs', [])[: self.limit]:
            jobs.append(canonicalize({
                'company_name': raw.get('company', ''),
                'job_title': raw.get('title', ''),
                'job_id': str(raw.get('id', '')),
                'category': raw.get('category', ''),
                'location': raw.get('candidate_required_location', ''),
                'job_type': raw.get('job_type', ''),
                'job_description': strip_html(raw.get('description', '')),
                'job_requirements': '',
                'apply_url': raw.get('url', ''),
                'source_url': raw.get('url', ''),
                'publication_date': raw.get('publication_date', ''),
                'salary': raw.get('salary', ''),
            }))
        logger.info(
            f"remotive 源: {len(jobs)} 个岗位"
            + (f"（search={self.search!r}）" if self.search else '')
        )
        return jobs
