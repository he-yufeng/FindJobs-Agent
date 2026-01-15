#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多公司招聘信息爬虫 - 完整版
支持国内大厂和外企的校招/社招岗位
"""

import json
import time
import random
import logging
import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod

import requests
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# User-Agent 池
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# 通用请求头
DEFAULT_HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
}

# 代理设置
PROXY = None  # {'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'}


class JobCrawlerBase(ABC):
    """爬虫基类"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.session.headers['User-Agent'] = random.choice(USER_AGENTS)
        self.jobs: List[Dict] = []
    
    @property
    @abstractmethod
    def company_name(self) -> str:
        pass
    
    @abstractmethod
    def crawl(self) -> List[Dict]:
        pass
    
    def _request(self, url: str, method: str = 'GET', **kwargs) -> Optional[requests.Response]:
        """发送请求"""
        max_retries = 3
        # 确保 Headers 中有 User-Agent
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        if 'User-Agent' not in kwargs['headers'] and 'User-Agent' not in self.session.headers:
            kwargs['headers']['User-Agent'] = random.choice(USER_AGENTS)

        for i in range(max_retries):
            try:
                # 随机延时，避免过快被封
                time.sleep(random.uniform(1.0, 3.0))
                
                if PROXY:
                    kwargs['proxies'] = PROXY
                kwargs['verify'] = False
                kwargs['timeout'] = kwargs.get('timeout', 30)
                
                if method.upper() == 'GET':
                    resp = self.session.get(url, **kwargs)
                else:
                    resp = self.session.post(url, **kwargs)
                
                # 处理 429 Too Many Requests 或 403 Forbidden
                if resp.status_code in [429, 403]:
                    logger.warning(f"触发反爬 ({resp.status_code})，等待重试: {url[:60]}...")
                    time.sleep(random.uniform(5, 10) * (i + 1))  # 指数退避
                    continue
                    
                resp.raise_for_status()
                return resp
            except Exception as e:
                if i == max_retries - 1:
                    logger.warning(f"请求失败: {url[:80]}... - {str(e)[:50]}")
                time.sleep(random.uniform(2, 5))
        return None
    
    def _normalize_job(self, raw: Dict) -> Dict:
        """标准化岗位数据"""
        return {
            'company_name': self.company_name,
            'job_title': str(raw.get('job_title', '')).strip(),
            'job_id': str(raw.get('job_id', '')).strip(),
            'category': str(raw.get('category', '')).strip(),
            'location': str(raw.get('location', '')).strip(),
            'job_type': str(raw.get('job_type', '')).strip(),
            'special_program': str(raw.get('special_program', '')).strip(),
            'job_description': str(raw.get('job_description', '')).strip(),
            'job_requirements': str(raw.get('job_requirements', '')).strip(),
            'apply_url': str(raw.get('apply_url', '')).strip(),
            'source_url': str(raw.get('source_url', '')).strip(),
        }


# ==================== 国内大厂 ====================

class TencentCrawler(JobCrawlerBase):
    """腾讯"""
    
    @property
    def company_name(self) -> str:
        return "腾讯"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        # 社招
        social = self._crawl_type('social')
        logger.info(f"  社招: {len(social)} 个")
        
        # 校招
        campus = self._crawl_type('campus')
        logger.info(f"  校招: {len(campus)} 个")
        
        self.jobs = social + campus
        return self.jobs
    
    def _crawl_type(self, job_type: str) -> List[Dict]:
        jobs = []
        page = 1
        
        while True:
            url = "https://careers.tencent.com/tencentcareer/api/post/Query"
            params = {
                'timestamp': int(time.time() * 1000),
                'attrId': '1' if job_type == 'campus' else '',
                'pageIndex': page,
                'pageSize': 100,
                'language': 'zh-cn',
                'area': 'cn',
            }
            
            resp = self._request(url, params=params)
            if not resp:
                break
            
            try:
                data = resp.json()
                posts = data.get('Data', {}).get('Posts', [])
                if not posts:
                    break
                
                for post in posts:
                    jobs.append(self._normalize_job({
                        'job_title': post.get('RecruitPostName', ''),
                        'job_id': post.get('PostId', ''),
                        'category': '校招' if job_type == 'campus' else '社招',
                        'location': post.get('LocationName', ''),
                        'job_type': post.get('CategoryName', ''),
                        'special_program': post.get('BGName', ''),
                        'job_description': post.get('Responsibility', ''),
                        'job_requirements': post.get('Requirement', ''),
                        'apply_url': f"https://careers.tencent.com/jobdesc.html?postId={post.get('PostId', '')}",
                        'source_url': f"https://careers.tencent.com/jobdesc.html?postId={post.get('PostId', '')}",
                    }))
                
                if page * 100 >= data.get('Data', {}).get('Count', 0):
                    break
                page += 1
            except:
                break
        
        return jobs


class AlibabaCrawler(JobCrawlerBase):
    """阿里巴巴"""
    
    @property
    def company_name(self) -> str:
        return "阿里巴巴"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        page = 1
        
        while True:
            url = "https://talent.alibaba.com/off_campus/position/list"
            payload = {
                "pageSize": 50,
                "pageIndex": page,
                "language": "zh",
                "channel": "group_official_site",
            }
            headers = {**DEFAULT_HEADERS, 'Content-Type': 'application/json'}
            
            resp = self._request(url, method='POST', json=payload, headers=headers)
            if not resp:
                break
            
            try:
                data = resp.json()
                positions = data.get('content', {}).get('data', {}).get('page', {}).get('result', [])
                if not positions:
                    break
                
                for pos in positions:
                    all_jobs.append(self._normalize_job({
                        'job_title': pos.get('name', ''),
                        'job_id': pos.get('code', ''),
                        'category': '校招' if pos.get('isSchool') else '社招',
                        'location': ', '.join(pos.get('workLocations', [])) if pos.get('workLocations') else '',
                        'job_type': pos.get('jobCategory', {}).get('name', '') if isinstance(pos.get('jobCategory'), dict) else '',
                        'special_program': pos.get('department', {}).get('name', '') if isinstance(pos.get('department'), dict) else '',
                        'job_description': pos.get('description', ''),
                        'job_requirements': pos.get('requirement', ''),
                        'apply_url': f"https://talent.alibaba.com/off-campus/position-detail?positionId={pos.get('code', '')}",
                        'source_url': f"https://talent.alibaba.com/off-campus/position-detail?positionId={pos.get('code', '')}",
                    }))
                
                total_page = data.get('content', {}).get('data', {}).get('page', {}).get('totalPage', 0)
                if page >= total_page:
                    break
                page += 1
                logger.info(f"  已获取 {len(all_jobs)} 个岗位...")
            except:
                break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


class BaiduCrawler(JobCrawlerBase):
    """百度"""
    
    @property
    def company_name(self) -> str:
        return "百度"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        for recruit_type in ['SOCIAL', 'CAMPUS']:
            page = 1
            while True:
                url = "https://talent.baidu.com/httservice/getPostListNew"
                payload = {"recruitType": recruit_type, "pageSize": 50, "curPage": page}
                headers = {**DEFAULT_HEADERS, 'Content-Type': 'application/json'}
                
                resp = self._request(url, method='POST', json=payload, headers=headers)
                if not resp:
                    break
                
                try:
                    data = resp.json()
                    posts = data.get('data', {}).get('list', [])
                    if not posts:
                        break
                    
                    for post in posts:
                        all_jobs.append(self._normalize_job({
                            'job_title': post.get('name', ''),
                            'job_id': str(post.get('postId', '')),
                            'category': '校招' if recruit_type == 'CAMPUS' else '社招',
                            'location': post.get('workPlace', ''),
                            'job_type': post.get('serviceType', ''),
                            'special_program': post.get('education', ''),
                            'job_description': post.get('serviceCondition', ''),
                            'job_requirements': post.get('workContent', ''),
                            'apply_url': f"https://talent.baidu.com/jobs/detail/{post.get('postId', '')}",
                            'source_url': f"https://talent.baidu.com/jobs/detail/{post.get('postId', '')}",
                        }))
                    
                    if page * 50 >= data.get('data', {}).get('total', 0):
                        break
                    page += 1
                except:
                    break
            
            logger.info(f"  {recruit_type}: {len([j for j in all_jobs if ('校招' if recruit_type=='CAMPUS' else '社招') in j['category']])} 个")
        
        self.jobs = all_jobs
        return all_jobs


class MeituanCrawler(JobCrawlerBase):
    """美团"""
    
    @property
    def company_name(self) -> str:
        return "美团"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        for job_type in [1, 2]:  # 1=社招, 2=校招
            offset = 0
            while True:
                url = "https://zhaopin.meituan.com/api/recruitment/v2/jobs"
                params = {'limit': 50, 'offset': offset, 'jobType': job_type}
                
                resp = self._request(url, params=params)
                if not resp:
                    break
                
                try:
                    data = resp.json()
                    jobs = data.get('data', {}).get('list', [])
                    if not jobs:
                        break
                    
                    for job in jobs:
                        all_jobs.append(self._normalize_job({
                            'job_title': job.get('name', ''),
                            'job_id': str(job.get('id', '')),
                            'category': '校招' if job_type == 2 else '社招',
                            'location': job.get('city', ''),
                            'job_type': job.get('jobCategory', ''),
                            'special_program': job.get('orgName', ''),
                            'job_description': job.get('responsibility', ''),
                            'job_requirements': job.get('requirement', ''),
                            'apply_url': f"https://zhaopin.meituan.com/job-detail?jobId={job.get('id', '')}",
                            'source_url': f"https://zhaopin.meituan.com/job-detail?jobId={job.get('id', '')}",
                        }))
                    
                    if offset + 50 >= data.get('data', {}).get('total', 0):
                        break
                    offset += 50
                except:
                    break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


class JDCrawler(JobCrawlerBase):
    """京东"""
    
    @property
    def company_name(self) -> str:
        return "京东"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        page = 1
        
        while True:
            url = "https://zhaopin.jd.com/web/job/job_list"
            params = {'page': page, 'limit': 50}
            
            resp = self._request(url, params=params)
            if not resp:
                break
            
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('list', [])
                if not jobs:
                    break
                
                for job in jobs:
                    all_jobs.append(self._normalize_job({
                        'job_title': job.get('jobName', ''),
                        'job_id': str(job.get('jobId', '')),
                        'category': '社招',
                        'location': job.get('workCity', ''),
                        'job_type': job.get('jobType', ''),
                        'special_program': job.get('deptName', ''),
                        'job_description': job.get('jobDesc', ''),
                        'job_requirements': job.get('jobRequire', ''),
                        'apply_url': f"https://zhaopin.jd.com/web/job/job_detail?jobId={job.get('jobId', '')}",
                        'source_url': f"https://zhaopin.jd.com/web/job/job_detail?jobId={job.get('jobId', '')}",
                    }))
                
                if page * 50 >= data.get('data', {}).get('total', 0):
                    break
                page += 1
            except:
                break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


class NeteaseCrawler(JobCrawlerBase):
    """网易"""
    
    @property
    def company_name(self) -> str:
        return "网易"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        page = 1
        
        while True:
            url = "https://hr.163.com/api/hr163/position/queryPage"
            payload = {"currentPage": page, "pageSize": 100}
            headers = {**DEFAULT_HEADERS, 'Content-Type': 'application/json', 'Origin': 'https://hr.163.com'}
            
            resp = self._request(url, method='POST', json=payload, headers=headers)
            if not resp:
                break
            
            try:
                data = resp.json()
                if data.get('code') != 200:
                    break
                    
                positions = data.get('data', {}).get('list', [])
                if not positions:
                    break
                
                for pos in positions:
                    all_jobs.append(self._normalize_job({
                        'job_title': pos.get('name', ''),
                        'job_id': str(pos.get('id', '')),
                        'category': pos.get('recruitTypeName', '社招'),
                        'location': pos.get('workPlaceName', ''),
                        'job_type': pos.get('firstPostTypeName', ''),
                        'special_program': pos.get('deptName', ''),
                        'job_description': pos.get('requirement', ''),
                        'job_requirements': f"学历: {pos.get('educationName', '')}",
                        'apply_url': f"https://hr.163.com/position/detail.html?id={pos.get('id', '')}",
                        'source_url': f"https://hr.163.com/position/detail.html?id={pos.get('id', '')}",
                    }))
                
                if page >= data.get('data', {}).get('pages', 0):
                    break
                page += 1
            except:
                break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


class KuaishouCrawler(JobCrawlerBase):
    """快手"""
    
    @property
    def company_name(self) -> str:
        return "快手"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        page = 1
        
        while True:
            url = "https://zhaopin.kuaishou.cn/recruit/api/job/list"
            params = {'page': page, 'pageSize': 50, 'workCity': '', 'jobType': ''}
            
            resp = self._request(url, params=params)
            if not resp:
                break
            
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('jobList', [])
                if not jobs:
                    break
                
                for job in jobs:
                    all_jobs.append(self._normalize_job({
                        'job_title': job.get('jobName', ''),
                        'job_id': str(job.get('jobId', '')),
                        'category': job.get('jobType', '社招'),
                        'location': job.get('workCity', ''),
                        'job_type': job.get('jobCategory', ''),
                        'special_program': job.get('deptName', ''),
                        'job_description': job.get('jobResponsibility', ''),
                        'job_requirements': job.get('jobRequirements', ''),
                        'apply_url': f"https://zhaopin.kuaishou.cn/recruit/e/#/official/jobs/detail/{job.get('jobId', '')}",
                        'source_url': f"https://zhaopin.kuaishou.cn/recruit/e/#/official/jobs/detail/{job.get('jobId', '')}",
                    }))
                
                if page * 50 >= data.get('data', {}).get('total', 0):
                    break
                page += 1
            except:
                break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


class XiaomiCrawler(JobCrawlerBase):
    """小米"""
    
    @property
    def company_name(self) -> str:
        return "小米"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        page = 1
        
        while True:
            url = "https://hr.xiaomi.com/api/position/list"
            params = {'pageNum': page, 'pageSize': 50}
            
            resp = self._request(url, params=params)
            if not resp:
                break
            
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('rows', [])
                if not jobs:
                    break
                
                for job in jobs:
                    all_jobs.append(self._normalize_job({
                        'job_title': job.get('positionName', ''),
                        'job_id': str(job.get('id', '')),
                        'category': job.get('recruitType', '社招'),
                        'location': job.get('workCity', ''),
                        'job_type': job.get('categoryName', ''),
                        'special_program': job.get('deptName', ''),
                        'job_description': job.get('requirement', ''),
                        'job_requirements': job.get('description', ''),
                        'apply_url': f"https://hr.xiaomi.com/position/{job.get('id', '')}",
                        'source_url': f"https://hr.xiaomi.com/position/{job.get('id', '')}",
                    }))
                
                if page * 50 >= data.get('data', {}).get('total', 0):
                    break
                page += 1
            except:
                break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


class BilibiliCrawler(JobCrawlerBase):
    """B站"""
    
    @property
    def company_name(self) -> str:
        return "哔哩哔哩"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        page = 1
        
        while True:
            url = "https://jobs.bilibili.com/api/positions"
            params = {'page': page, 'pageSize': 50}
            
            resp = self._request(url, params=params)
            if not resp:
                break
            
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('list', [])
                if not jobs:
                    break
                
                for job in jobs:
                    all_jobs.append(self._normalize_job({
                        'job_title': job.get('name', ''),
                        'job_id': str(job.get('id', '')),
                        'category': job.get('type', '社招'),
                        'location': job.get('city', ''),
                        'job_type': job.get('category', ''),
                        'special_program': job.get('department', ''),
                        'job_description': job.get('description', ''),
                        'job_requirements': job.get('requirement', ''),
                        'apply_url': f"https://jobs.bilibili.com/position/{job.get('id', '')}",
                        'source_url': f"https://jobs.bilibili.com/position/{job.get('id', '')}",
                    }))
                
                if page * 50 >= data.get('data', {}).get('total', 0):
                    break
                page += 1
            except:
                break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


class DidiCrawler(JobCrawlerBase):
    """滴滴"""
    
    @property
    def company_name(self) -> str:
        return "滴滴"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        page = 1
        
        while True:
            url = "https://talent.didiglobal.com/api/jobList"
            params = {'page': page, 'pageSize': 50, 'language': 'zh'}
            
            resp = self._request(url, params=params)
            if not resp:
                break
            
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('list', [])
                if not jobs:
                    break
                
                for job in jobs:
                    all_jobs.append(self._normalize_job({
                        'job_title': job.get('name', ''),
                        'job_id': str(job.get('id', '')),
                        'category': job.get('recruitType', '社招'),
                        'location': job.get('city', ''),
                        'job_type': job.get('category', ''),
                        'special_program': job.get('department', ''),
                        'job_description': job.get('description', ''),
                        'job_requirements': job.get('requirement', ''),
                        'apply_url': f"https://talent.didiglobal.com/position/{job.get('id', '')}",
                        'source_url': f"https://talent.didiglobal.com/position/{job.get('id', '')}",
                    }))
                
                if page * 50 >= data.get('data', {}).get('total', 0):
                    break
                page += 1
            except:
                break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


class PinduoduoCrawler(JobCrawlerBase):
    """拼多多"""
    
    @property
    def company_name(self) -> str:
        return "拼多多"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        page = 1
        
        while True:
            url = "https://careers.pinduoduo.com/api/position/list"
            params = {'page': page, 'pageSize': 50}
            
            resp = self._request(url, params=params)
            if not resp:
                break
            
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('list', [])
                if not jobs:
                    break
                
                for job in jobs:
                    all_jobs.append(self._normalize_job({
                        'job_title': job.get('name', ''),
                        'job_id': str(job.get('id', '')),
                        'category': job.get('type', '社招'),
                        'location': job.get('city', ''),
                        'job_type': job.get('category', ''),
                        'special_program': job.get('department', ''),
                        'job_description': job.get('description', ''),
                        'job_requirements': job.get('requirement', ''),
                        'apply_url': f"https://careers.pinduoduo.com/position/{job.get('id', '')}",
                        'source_url': f"https://careers.pinduoduo.com/position/{job.get('id', '')}",
                    }))
                
                if page * 50 >= data.get('data', {}).get('total', 0):
                    break
                page += 1
            except:
                break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


class HuaweiCrawler(JobCrawlerBase):
    """华为"""
    
    @property
    def company_name(self) -> str:
        return "华为"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        page = 1
        
        while True:
            url = "https://career.huawei.com/reccampportal/portal5/position/api/position/queryPositions"
            payload = {"pageIndex": page, "pageSize": 50, "positionType": "", "keyWord": ""}
            headers = {**DEFAULT_HEADERS, 'Content-Type': 'application/json'}
            
            resp = self._request(url, method='POST', json=payload, headers=headers)
            if not resp:
                break
            
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('list', [])
                if not jobs:
                    break
                
                for job in jobs:
                    all_jobs.append(self._normalize_job({
                        'job_title': job.get('positionName', ''),
                        'job_id': str(job.get('positionId', '')),
                        'category': job.get('positionType', ''),
                        'location': job.get('workLocation', ''),
                        'job_type': job.get('jobType', ''),
                        'special_program': job.get('department', ''),
                        'job_description': job.get('requirement', ''),
                        'job_requirements': job.get('description', ''),
                        'apply_url': f"https://career.huawei.com/reccampportal/campus/position/{job.get('positionId', '')}",
                        'source_url': f"https://career.huawei.com/reccampportal/campus/position/{job.get('positionId', '')}",
                    }))
                
                if page * 50 >= data.get('data', {}).get('total', 0):
                    break
                page += 1
            except:
                break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


class ByteDanceCrawler(JobCrawlerBase):
    """字节跳动"""
    
    @property
    def company_name(self) -> str:
        return "字节跳动"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        # 初始化 Session，尝试获取 CSRF Token
        self.session.headers.update({
            "Referer": "https://jobs.bytedance.com/experienced/position",
            "Origin": "https://jobs.bytedance.com"
        })
        try:
            # 预热，尝试获取 cookie
            self._request("https://jobs.bytedance.com/experienced/position", timeout=10)
            # 尝试查找 csrf token
            csrf_token = None
            for cookie in self.session.cookies:
                if 'csrf' in cookie.name.lower():
                    csrf_token = cookie.value
                    break
            if csrf_token:
                self.session.headers.update({"x-csrf-token": csrf_token})
        except:
            pass

        all_jobs = []
        offset = 0
        limit = 20  # 字节 API 通常分页较小
        
        while True:
            url = "https://jobs.bytedance.com/api/v1/search/external/posts"
            payload = {
                "limit": limit,
                "offset": offset,
                "keyword": "",
                "attribute_code_list": [] 
            }
            
            resp = self._request(url, method='POST', json=payload)
            if not resp:
                if offset == 0:
                    logger.warning("无法连接字节跳动 API，可能是网络限制或反爬策略更新")
                break
            
            try:
                data = resp.json()
                jobs = data.get('posts', [])
                if not jobs:
                    break
                
                for job in jobs:
                    # 提取城市信息
                    city_list = []
                    if job.get('city_info'):
                        city_list = [c.get('name', '') for c in job.get('city_info') if isinstance(c, dict)]
                    
                    # 提取职位类别
                    job_cat = ''
                    if isinstance(job.get('job_category'), dict):
                        job_cat = job.get('job_category', {}).get('name', '')
                        
                    # 提取招聘类型 (社招/校招)
                    recruit_type = '社招'
                    if isinstance(job.get('recruit_type'), dict):
                        recruit_type = job.get('recruit_type', {}).get('name', '')

                    all_jobs.append(self._normalize_job({
                        'job_title': job.get('title', ''),
                        'job_id': job.get('id', ''),
                        'category': recruit_type,
                        'location': ', '.join(city_list),
                        'job_type': job_cat,
                        'special_program': str(job.get('sub_job_category_list', [])),
                        'job_description': job.get('description', ''),
                        'job_requirements': job.get('requirement', ''),
                        'apply_url': f"https://jobs.bytedance.com/experienced/position/{job.get('id', '')}",
                        'source_url': f"https://jobs.bytedance.com/experienced/position/{job.get('id', '')}",
                    }))
                
                count = data.get('count', 0)
                if offset + limit >= count:
                    break
                
                offset += limit
                logger.info(f"  已获取 {len(all_jobs)}/{count} 个岗位...")
                
                # 字节反爬较严，增加额外随机延时
                time.sleep(random.uniform(1.0, 2.5))
                
            except Exception as e:
                logger.error(f"解析字节跳动数据出错: {e}")
                break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


# ==================== 外企 ====================

class MicrosoftCrawler(JobCrawlerBase):
    """微软"""
    
    @property
    def company_name(self) -> str:
        return "Microsoft"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        skip = 0
        
        while True:
            url = "https://gcsservices.careers.microsoft.com/search/api/v1/search"
            params = {'l': 'zh_cn', 'pg': skip // 100 + 1, 'pgSz': 100, 'o': skip, 'flt': 'true'}
            
            resp = self._request(url, params=params)
            if not resp:
                break
            
            try:
                data = resp.json()
                jobs = data.get('operationResult', {}).get('result', {}).get('jobs', [])
                if not jobs:
                    break
                
                for job in jobs:
                    props = job.get('properties', {})
                    all_jobs.append(self._normalize_job({
                        'job_title': job.get('title', ''),
                        'job_id': job.get('jobId', ''),
                        'category': props.get('employmentType', ''),
                        'location': ', '.join(props.get('locations', [])) if props.get('locations') else '',
                        'job_type': props.get('discipline', ''),
                        'special_program': props.get('subDiscipline', ''),
                        'job_description': job.get('description', ''),
                        'apply_url': f"https://jobs.careers.microsoft.com/global/en/job/{job.get('jobId', '')}",
                        'source_url': f"https://jobs.careers.microsoft.com/global/en/job/{job.get('jobId', '')}",
                    }))
                
                total = data.get('operationResult', {}).get('result', {}).get('totalJobs', 0)
                if skip + 100 >= total:
                    break
                skip += 100
                logger.info(f"  已获取 {len(all_jobs)}/{total} 个岗位...")
            except:
                break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


class GoogleCrawler(JobCrawlerBase):
    """Google"""
    
    @property
    def company_name(self) -> str:
        return "Google"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        page_token = ""
        
        while True:
            url = "https://careers.google.com/api/v3/search/"
            params = {
                'company': 'Google',
                'hl': 'zh_CN',
                'jlo': 'zh_CN',
                'location': 'China',
                'page_size': 100,
                'q': '',
            }
            if page_token:
                params['page_token'] = page_token
            
            resp = self._request(url, params=params)
            if not resp:
                break
            
            try:
                data = resp.json()
                jobs = data.get('jobs', [])
                if not jobs:
                    break
                
                for job in jobs:
                    locs = [loc.get('display', '') for loc in job.get('locations', [])]
                    all_jobs.append(self._normalize_job({
                        'job_title': job.get('title', ''),
                        'job_id': job.get('id', ''),
                        'category': 'Full-time',
                        'location': ', '.join(locs),
                        'job_type': ', '.join(job.get('categories', [])),
                        'job_description': job.get('description', ''),
                        'job_requirements': job.get('qualifications', ''),
                        'apply_url': job.get('apply_url', ''),
                        'source_url': f"https://careers.google.com/jobs/results/{job.get('id', '')}",
                    }))
                
                page_token = data.get('next_page_token', '')
                if not page_token:
                    break
                logger.info(f"  已获取 {len(all_jobs)} 个岗位...")
            except:
                break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


class AmazonCrawler(JobCrawlerBase):
    """Amazon"""
    
    @property
    def company_name(self) -> str:
        return "Amazon"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        offset = 0
        
        while True:
            url = "https://www.amazon.jobs/zh/search.json"
            params = {'offset': offset, 'result_limit': 100, 'sort': 'recent', 'country': 'CHN'}
            
            resp = self._request(url, params=params)
            if not resp:
                break
            
            try:
                data = resp.json()
                jobs = data.get('jobs', [])
                if not jobs:
                    break
                
                for job in jobs:
                    all_jobs.append(self._normalize_job({
                        'job_title': job.get('title', ''),
                        'job_id': str(job.get('id_icims', '')),
                        'category': job.get('job_category', ''),
                        'location': job.get('location', ''),
                        'job_type': job.get('primary_search_label', ''),
                        'special_program': job.get('business_category', ''),
                        'job_description': job.get('description_short', ''),
                        'job_requirements': job.get('basic_qualifications', ''),
                        'apply_url': f"https://www.amazon.jobs{job.get('job_path', '')}",
                        'source_url': f"https://www.amazon.jobs{job.get('job_path', '')}",
                    }))
                
                total = data.get('hits', 0)
                if offset + 100 >= total:
                    break
                offset += 100
                logger.info(f"  已获取 {len(all_jobs)}/{total} 个岗位...")
            except:
                break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


class MetaCrawler(JobCrawlerBase):
    """Meta/Facebook"""
    
    @property
    def company_name(self) -> str:
        return "Meta"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        page = 0
        
        while True:
            url = "https://www.metacareers.com/graphql"
            payload = {
                "variables": {
                    "search_input": {
                        "q": "",
                        "divisions": [],
                        "offices": [],
                        "roles": [],
                        "leadership_levels": [],
                        "saved_jobs": [],
                        "is_remote_only": False,
                        "sort_by_new": False,
                        "page": page,
                    }
                },
                "doc_id": "5765033286855011"  # Meta careers GraphQL doc_id
            }
            headers = {**DEFAULT_HEADERS, 'Content-Type': 'application/json'}
            
            resp = self._request(url, method='POST', json=payload, headers=headers)
            if not resp:
                break
            
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('job_search', {}).get('results', [])
                if not jobs:
                    break
                
                for job in jobs:
                    all_jobs.append(self._normalize_job({
                        'job_title': job.get('title', ''),
                        'job_id': job.get('id', ''),
                        'category': 'Full-time',
                        'location': ', '.join([o.get('city', '') for o in job.get('offices', [])]),
                        'job_type': ', '.join([t.get('name', '') for t in job.get('teams', [])]),
                        'job_description': job.get('short_description', ''),
                        'apply_url': f"https://www.metacareers.com/jobs/{job.get('id', '')}",
                        'source_url': f"https://www.metacareers.com/jobs/{job.get('id', '')}",
                    }))
                
                if len(jobs) < 20:
                    break
                page += 1
            except:
                break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


class AppleCrawler(JobCrawlerBase):
    """Apple"""
    
    @property
    def company_name(self) -> str:
        return "Apple"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        page = 1
        
        while True:
            url = f"https://jobs.apple.com/api/role/search"
            params = {
                'location': 'china-CHNC',
                'page': page,
            }
            
            resp = self._request(url, params=params)
            if not resp:
                break
            
            try:
                data = resp.json()
                jobs = data.get('searchResults', [])
                if not jobs:
                    break
                
                for job in jobs:
                    locs = job.get('locations', [])
                    loc_str = ', '.join([l.get('name', '') for l in locs]) if isinstance(locs, list) else ''
                    
                    all_jobs.append(self._normalize_job({
                        'job_title': job.get('postingTitle', ''),
                        'job_id': job.get('positionId', ''),
                        'category': job.get('jobType', ''),
                        'location': loc_str,
                        'job_type': job.get('team', {}).get('teamName', '') if isinstance(job.get('team'), dict) else '',
                        'apply_url': f"https://jobs.apple.com/zh-cn/details/{job.get('positionId', '')}",
                        'source_url': f"https://jobs.apple.com/zh-cn/details/{job.get('positionId', '')}",
                    }))
                
                total = data.get('totalRecords', 0)
                if len(all_jobs) >= total:
                    break
                page += 1
                logger.info(f"  已获取 {len(all_jobs)}/{total} 个岗位...")
            except:
                break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


class NvidiaCrawler(JobCrawlerBase):
    """Nvidia"""
    
    @property
    def company_name(self) -> str:
        return "Nvidia"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        page = 1
        
        while True:
            url = "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs"
            payload = {
                "appliedFacets": {"locations": ["91336993fab910af6d70c912035a4390"]},  # China
                "limit": 50,
                "offset": (page - 1) * 50,
                "searchText": ""
            }
            headers = {**DEFAULT_HEADERS, 'Content-Type': 'application/json'}
            
            resp = self._request(url, method='POST', json=payload, headers=headers)
            if not resp:
                break
            
            try:
                data = resp.json()
                jobs = data.get('jobPostings', [])
                if not jobs:
                    break
                
                for job in jobs:
                    all_jobs.append(self._normalize_job({
                        'job_title': job.get('title', ''),
                        'job_id': job.get('bulletFields', [''])[0] if job.get('bulletFields') else '',
                        'category': 'Full-time',
                        'location': job.get('locationsText', ''),
                        'job_type': job.get('postedOn', ''),
                        'apply_url': f"https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite{job.get('externalPath', '')}",
                        'source_url': f"https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite{job.get('externalPath', '')}",
                    }))
                
                total = data.get('total', 0)
                if page * 50 >= total:
                    break
                page += 1
            except:
                break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


class IntelCrawler(JobCrawlerBase):
    """Intel"""
    
    @property
    def company_name(self) -> str:
        return "Intel"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name}...")
        
        all_jobs = []
        page = 0
        
        while True:
            url = "https://jobs.intel.com/api/jobs"
            params = {
                'country': 'China',
                'page': page,
                'limit': 50,
                'sortBy': 'relevance',
            }
            
            resp = self._request(url, params=params)
            if not resp:
                break
            
            try:
                data = resp.json()
                jobs = data.get('jobs', [])
                if not jobs:
                    break
                
                for job in jobs:
                    all_jobs.append(self._normalize_job({
                        'job_title': job.get('title', ''),
                        'job_id': job.get('id', ''),
                        'category': job.get('employment_type', ''),
                        'location': job.get('location', ''),
                        'job_type': job.get('categories', [''])[0] if job.get('categories') else '',
                        'job_description': job.get('description', ''),
                        'apply_url': job.get('absolute_url', ''),
                        'source_url': job.get('absolute_url', ''),
                    }))
                
                if (page + 1) * 50 >= data.get('count', 0):
                    break
                page += 1
            except:
                break
        
        self.jobs = all_jobs
        logger.info(f"  共获取 {len(all_jobs)} 个岗位")
        return all_jobs


# ==================== 爬虫注册 ====================

CRAWLER_REGISTRY = {
    # 国内大厂
    'tencent': TencentCrawler,
    'alibaba': AlibabaCrawler,
    'baidu': BaiduCrawler,
    'meituan': MeituanCrawler,
    'jd': JDCrawler,
    'netease': NeteaseCrawler,
    'kuaishou': KuaishouCrawler,
    'xiaomi': XiaomiCrawler,
    'bilibili': BilibiliCrawler,
    'didi': DidiCrawler,
    'pinduoduo': PinduoduoCrawler,
    'huawei': HuaweiCrawler,
    'bytedance': ByteDanceCrawler,
    # 外企
    'microsoft': MicrosoftCrawler,
    'google': GoogleCrawler,
    'amazon': AmazonCrawler,
    'meta': MetaCrawler,
    'apple': AppleCrawler,
    'nvidia': NvidiaCrawler,
    'intel': IntelCrawler,
}


class MultiCompanyCrawler:
    """多公司爬虫管理器"""
    
    def __init__(self, companies: List[str] = None, output_dir: str = '.'):
        self.companies = companies or list(CRAWLER_REGISTRY.keys())
        self.output_dir = Path(output_dir)
        self.all_jobs: List[Dict] = []
        
    def crawl_all(self) -> List[Dict]:
        logger.info(f"\n{'='*60}")
        logger.info(f"准备爬取 {len(self.companies)} 家公司")
        logger.info(f"{'='*60}\n")
        
        for company in self.companies:
            if company not in CRAWLER_REGISTRY:
                logger.warning(f"未知公司: {company}")
                continue
            
            try:
                crawler = CRAWLER_REGISTRY[company]()
                jobs = crawler.crawl()
                self.all_jobs.extend(jobs)
            except Exception as e:
                logger.error(f"爬取 {company} 失败: {e}")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"爬取完成! 共获取 {len(self.all_jobs)} 个岗位")
        logger.info(f"{'='*60}")
        
        return self.all_jobs
    
    def save(self, filename: str = None) -> str:
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"all_jobs_{timestamp}.json"
        
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.all_jobs, f, ensure_ascii=False, indent=2)
        
        logger.info(f"数据已保存到: {output_path}")
        self._print_statistics()
        return str(output_path)
    
    def _print_statistics(self):
        from collections import Counter
        company_counts = Counter(job['company_name'] for job in self.all_jobs)
        
        logger.info("\n📊 按公司统计:")
        logger.info("-" * 40)
        for company, count in sorted(company_counts.items(), key=lambda x: -x[1]):
            logger.info(f"  {company:15} : {count:5} 个岗位")
        logger.info("-" * 40)


def main():
    parser = argparse.ArgumentParser(description='多公司招聘信息爬虫')
    parser.add_argument('--companies', '-c', nargs='+', default=['all'])
    parser.add_argument('--output', '-o', default='.')
    parser.add_argument('--filename', '-f', default=None)
    parser.add_argument('--list', '-l', action='store_true')
    
    args = parser.parse_args()
    
    if args.list:
        print("\n" + "="*50)
        print("支持的公司列表")
        print("="*50)
        print("\n【国内大厂】")
        domestic = ['tencent', 'alibaba', 'baidu', 'meituan', 'jd', 'netease', 
                    'kuaishou', 'xiaomi', 'bilibili', 'didi', 'pinduoduo', 'huawei', 'bytedance']
        for name in domestic:
            if name in CRAWLER_REGISTRY:
                print(f"  {name:15} -> {CRAWLER_REGISTRY[name]().company_name}")
        
        print("\n【外企】")
        foreign = ['microsoft', 'google', 'amazon', 'meta', 'apple', 'nvidia', 'intel']
        for name in foreign:
            if name in CRAWLER_REGISTRY:
                print(f"  {name:15} -> {CRAWLER_REGISTRY[name]().company_name}")
        
        print("\n" + "="*50)
        print("使用示例:")
        print("  python job_crawler.py -c tencent alibaba microsoft")
        print("  python job_crawler.py -c all -f all_jobs.json")
        print("="*50)
        return
    
    companies = None if 'all' in args.companies else args.companies
    
    crawler = MultiCompanyCrawler(companies=companies, output_dir=args.output)
    crawler.crawl_all()
    crawler.save(filename=args.filename)


if __name__ == '__main__':
    main()
