#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""freehire.me 岗位源适配器

freehire 是开源的 IT 职位聚合器，公开 API 免 key。走 /agent/jobs/search，
结果自带完整 markdown JD 和公司官方 ATS 投递链接，不用再抓详情页。
筛选词表（skill slug、国家码、枚举）运行时从 /jobs/facets 拉，不硬编码。
文档: https://freehire.me/docs/api
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from job_crawler_v2 import JobCrawlerBase, MAX_JOBS_PER_COMPANY

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent

FREEHIRE_BASE_URL = 'https://freehire.me/api/v1'

# freehire 侧约定调用方自报家门，429 之前他们好先打招呼
FREEHIRE_UA = 'FindJobs-Agent/freehire-source (+https://github.com/he-yufeng/FindJobs-Agent)'

# API 硬性约束：offset + limit 不能超过 10000
MAX_OFFSET_WINDOW = 10000


class FreehireAPIError(Exception):
    """freehire 请求重试耗尽，或返回了不该重试的 4xx"""


class FreehireCrawler(JobCrawlerBase):
    """freehire.me 聚合源。定位是补充现有公司爬虫，只收 IT/tech 岗位"""

    def __init__(
        self,
        max_jobs: int = MAX_JOBS_PER_COMPANY,
        query: str = '',
        skills: Optional[List[str]] = None,
        countries: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
        cities: Optional[List[str]] = None,
        work_mode: Optional[List[str]] = None,
        seniority: Optional[List[str]] = None,
        skills_and: bool = False,
        posted_within_days: Optional[int] = None,
        tech_only: bool = True,
        page_size: int = 100,
        request_interval: float = 1.0,
        timeout: int = 20,
        max_retries: int = 3,
    ):
        super().__init__(max_jobs=max_jobs)
        self.session.headers.update({'User-Agent': FREEHIRE_UA})
        self.query = query
        self.skills = list(skills or [])
        self.countries = list(countries or [])
        self.regions = list(regions or [])
        self.cities = list(cities or [])
        self.work_mode = list(work_mode or [])
        self.seniority = list(seniority or [])
        self.skills_and = skills_and
        self.posted_within_days = posted_within_days
        self.tech_only = tech_only
        self.page_size = min(page_size, 100)
        self.request_interval = request_interval
        self.timeout = timeout
        self.max_retries = max_retries
        self._last_request_ts = 0.0
        self._resolved_skills: Optional[List[str]] = None
        self._facets_cache: Dict[Optional[tuple], Dict[str, Dict[str, int]]] = {}

    @property
    def company_name(self) -> str:
        return 'freehire'

    # ---------- HTTP ----------

    def _pace(self) -> None:
        """礼貌间隔：两次请求之间至少隔 request_interval 秒"""
        if self.request_interval <= 0:
            return
        wait = self.request_interval - (time.monotonic() - self._last_request_ts)
        if wait > 0:
            time.sleep(wait)

    def _note_rate_headers(self, resp: requests.Response) -> None:
        """响应里带额度水位，见底了主动睡到 reset，别等 429"""
        remaining = resp.headers.get('X-RateLimit-Remaining')
        reset = resp.headers.get('X-RateLimit-Reset')
        if remaining is None or reset is None:
            return
        try:
            if int(float(remaining)) <= 0:
                wait = min(float(reset), 60.0)
                if wait > 0:
                    logger.info(f"freehire 限流额度见底，等 {wait:.0f}s")
                    time.sleep(wait)
        except ValueError:
            pass

    def _get(self, path: str, params: Optional[Dict] = None) -> Dict:
        """GET 一个 JSON。429/5xx/网络错误按指数退避重试，其他 4xx 直接抛"""
        url = f'{FREEHIRE_BASE_URL}{path}'
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            self._pace()
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as e:
                last_exc = e
                time.sleep(min(2 ** attempt, 30))
                continue
            finally:
                self._last_request_ts = time.monotonic()
            self._note_rate_headers(resp)
            if resp.status_code == 429:
                retry_after = resp.headers.get('Retry-After')
                try:
                    wait = float(retry_after) if retry_after else float(min(2 ** attempt, 30))
                except ValueError:
                    wait = float(min(2 ** attempt, 30))
                logger.warning(f"freehire 429，等 {wait:.0f}s 后重试")
                last_exc = FreehireAPIError(f'GET {path} 触发限流')
                time.sleep(min(wait, 60.0))
                continue
            if 500 <= resp.status_code < 600:
                last_exc = FreehireAPIError(f'GET {path} -> {resp.status_code}')
                time.sleep(min(2 ** attempt, 30))
                continue
            if resp.status_code >= 400:
                # 4xx 多半是参数问题，重试没意义
                raise FreehireAPIError(f'GET {path} -> {resp.status_code}: {resp.text[:200]}')
            try:
                return resp.json()
            except ValueError as e:
                last_exc = FreehireAPIError(f'GET {path} 返回的不是 JSON')
                logger.debug(f"freehire 响应解析失败: {e}")
                time.sleep(min(2 ** attempt, 30))
        raise FreehireAPIError(f'GET {path} 重试 {self.max_retries + 1} 次仍失败') from last_exc

    # ---------- facets：运行时发现筛选词表 ----------

    def get_facets(self, facets: Optional[List[str]] = None, force_refresh: bool = False) -> Dict[str, Dict[str, int]]:
        """拉实时筛选词表，按所选 facet 组合缓存。返回 {facet: {值: 岗位数}}"""
        key = tuple(sorted(facets)) if facets else None
        if not force_refresh and key in self._facets_cache:
            return self._facets_cache[key]
        params = {'facets': ','.join(facets)} if facets else None
        payload = self._get('/jobs/facets', params)
        result = (payload.get('data') or {}).get('facets') or {}
        self._facets_cache[key] = result
        return result

    def facet_values(self, name: str) -> Dict[str, int]:
        return self.get_facets(facets=[name]).get(name) or {}

    def _resolve_skills(self) -> List[str]:
        """把用户给的技能名对齐到 canonical slug。词表拉不到就原样透传"""
        if not self.skills:
            return []
        if self._resolved_skills is not None:
            return self._resolved_skills
        try:
            vocab = self.facet_values('skills')
        except FreehireAPIError as e:
            logger.warning(f"freehire 词表拉取失败，技能按原样传递: {e}")
            vocab = {}
        lower = {slug.lower(): slug for slug in vocab}
        resolved = []
        for s in self.skills:
            if s in vocab:
                resolved.append(s)
            elif s.lower() in lower:
                resolved.append(lower[s.lower()])
            else:
                # API 对未知值不报错，只是静默匹配不到，提个醒
                logger.warning(f"未知 skill slug '{s}'，freehire 会匹配不到任何岗位")
                resolved.append(s)
        self._resolved_skills = resolved
        return resolved

    # ---------- 搜索与映射 ----------

    def _build_params(self, limit: int, offset: int) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            'limit': limit,
            'offset': offset,
            'description_format': 'markdown',
        }
        if self.query:
            params['q'] = self.query
        if self.tech_only:
            params['is_tech'] = 'tech'
        skills = self._resolve_skills()
        if skills:
            params['skills'] = skills
            if self.skills_and:
                params['skills_mode'] = 'and'
        if self.countries:
            params['countries'] = self.countries
        if self.regions:
            params['regions'] = self.regions
        if self.cities:
            params['cities'] = self.cities
        if self.work_mode:
            params['work_mode'] = self.work_mode
        if self.seniority:
            params['seniority'] = self.seniority
        if self.posted_within_days:
            params['posted_within_days'] = self.posted_within_days
        return params

    def _map_job(self, raw: Dict) -> Dict:
        slug = str(raw.get('public_slug', '') or '').strip()
        enrichment = raw.get('enrichment') or {}
        location = str(raw.get('location', '') or '').strip()
        if not location:
            places = (raw.get('cities') or []) + (raw.get('countries') or [])
            location = ', '.join(str(p) for p in places)
        return {
            'company_name': str(raw.get('company', '') or '').strip(),
            'job_title': raw.get('title', ''),
            'job_id': f'FH_{slug}' if slug else '',
            'category': enrichment.get('category', '') or '',
            'location': location,
            'job_type': enrichment.get('employment_type', '') or '',
            'special_program': '',
            # 完整 markdown JD，原样保留
            'job_description': raw.get('description', '') or '',
            'job_requirements': '',
            # 公司官方 ATS 投递链接
            'apply_url': raw.get('url', '') or '',
            'source_url': f'https://freehire.me/jobs/{slug}' if slug else '',
        }

    def _normalize_job(self, raw: Dict) -> Dict:
        job = super()._normalize_job(raw)
        # 聚合源的公司名跟着每条结果走，基类只会写死成爬虫名
        job['company_name'] = str(raw.get('company_name', '')).strip() or self.company_name
        return job

    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name} (freehire.me)...")
        offset = 0
        total: Optional[int] = None
        while len(self.jobs) < self.max_jobs:
            limit = min(self.page_size, self.max_jobs - len(self.jobs))
            if offset + limit > MAX_OFFSET_WINDOW:
                logger.warning(f"freehire 分页到达 {MAX_OFFSET_WINDOW} 上限，提前收尾")
                break
            try:
                payload = self._get('/agent/jobs/search', self._build_params(limit, offset))
            except FreehireAPIError as e:
                logger.error(f"freehire 拉取失败，保留已抓到的 {len(self.jobs)} 个: {e}")
                break
            data = payload.get('data') or []
            meta = payload.get('meta') or {}
            if meta.get('ignored_params'):
                logger.warning(f"freehire 忽略了这些参数: {meta['ignored_params']}")
            total = meta.get('total', total)
            if not data:
                break
            for raw in data:
                if len(self.jobs) >= self.max_jobs:
                    break
                self.jobs.append(self._normalize_job(self._map_job(raw)))
            offset += len(data)
            if len(data) < limit or (total is not None and offset >= total):
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


def _split(arg: str) -> List[str]:
    return [s.strip() for s in arg.split(',') if s.strip()]


def main():
    parser = argparse.ArgumentParser(description='freehire.me 岗位源（IT 职位聚合，免 API key）')
    parser.add_argument('-q', '--query', default='', help='全文关键词')
    parser.add_argument('--skills', default='', help='技能 slug，逗号分隔；合法值先用 --list-facets skills 查')
    parser.add_argument('--skills-and', action='store_true', help='多个技能从 OR 改成 AND')
    parser.add_argument('--countries', default='', help='国家码，逗号分隔，如 us,de')
    parser.add_argument('--regions', default='', help='大区，逗号分隔，如 eu,apac')
    parser.add_argument('--cities', default='', help='城市名，逗号分隔，如 London,Berlin')
    parser.add_argument('--work-mode', default='', help='remote/hybrid/onsite，逗号分隔')
    parser.add_argument('--seniority', default='', help='junior/senior/lead 等，逗号分隔')
    parser.add_argument('--posted-within-days', type=int, default=None, help='只取最近 N 天发布的')
    parser.add_argument('--include-non-tech', action='store_true', help='默认只收 tech 岗，加这个放开')
    parser.add_argument('-m', '--max', type=int, default=MAX_JOBS_PER_COMPANY, help='最大岗位数')
    parser.add_argument('-f', '--file', default='freehire_jobs_raw.json', help='输出文件')
    parser.add_argument('--list-facets', metavar='NAMES', default='',
                        help='打印实时筛选词表后退出，如 skills 或 skills,countries')
    args = parser.parse_args()

    crawler = FreehireCrawler(
        max_jobs=args.max,
        query=args.query,
        skills=_split(args.skills),
        countries=_split(args.countries),
        regions=_split(args.regions),
        cities=_split(args.cities),
        work_mode=_split(args.work_mode),
        seniority=_split(args.seniority),
        skills_and=args.skills_and,
        posted_within_days=args.posted_within_days,
        tech_only=not args.include_non_tech,
    )

    if args.list_facets:
        names = _split(args.list_facets)
        try:
            facets = crawler.get_facets(facets=names or None)
        except FreehireAPIError as e:
            logger.error(f"拉取词表失败: {e}")
            return
        for name, values in facets.items():
            print(f"\n[{name}] 共 {len(values)} 个值，按岗位数取前 50:")
            for value, count in sorted(values.items(), key=lambda x: -x[1])[:50]:
                print(f"  {value:30} {count}")
        return

    jobs = crawler.crawl()
    out = ROOT_DIR / args.file
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    logger.info(f"✅ {len(jobs)} 个岗位已保存到: {out}")


if __name__ == '__main__':
    main()
