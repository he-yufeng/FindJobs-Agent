#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多公司招聘信息爬虫 v2
每家公司限制300个岗位，支持更多公司
"""

import json
import time
import random
import logging
import argparse
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent

# 每家公司最大岗位数
MAX_JOBS_PER_COMPANY = 300

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

# Selenium支持
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.warning("Selenium不可用，部分公司将无法爬取")


class JobCrawlerBase(ABC):
    """爬虫基类"""
    
    def __init__(self, max_jobs: int = MAX_JOBS_PER_COMPANY):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.jobs: List[Dict] = []
        self.max_jobs = max_jobs
    
    @property
    @abstractmethod
    def company_name(self) -> str:
        pass
    
    @abstractmethod
    def crawl(self) -> List[Dict]:
        pass
    
    def _request(self, url: str, method: str = 'GET', **kwargs) -> Optional[requests.Response]:
        for i in range(3):
            try:
                time.sleep(random.uniform(0.2, 0.5))
                kwargs['verify'] = False
                kwargs['timeout'] = kwargs.get('timeout', 20)
                resp = self.session.get(url, **kwargs) if method == 'GET' else self.session.post(url, **kwargs)
                resp.raise_for_status()
                return resp
            except Exception as e:
                if i == 2:
                    logger.debug(f"请求失败 [{self.company_name}]: {str(e)[:50]}")
                time.sleep(1)
        return None
    
    def _normalize_job(self, raw: Dict) -> Dict:
        job_id = raw.get('job_id', '')
        if not job_id:
            content = f"{self.company_name}_{raw.get('job_title', '')}_{raw.get('location', '')}"
            job_id = hashlib.md5(content.encode()).hexdigest()[:12]
        return {
            'company_name': self.company_name,
            'job_title': str(raw.get('job_title', '')).strip(),
            'job_id': str(job_id).strip(),
            'category': str(raw.get('category', '')).strip(),
            'location': str(raw.get('location', '')).strip(),
            'job_type': str(raw.get('job_type', '')).strip(),
            'special_program': str(raw.get('special_program', '')).strip(),
            'job_description': str(raw.get('job_description', '')).strip(),
            'job_requirements': str(raw.get('job_requirements', '')).strip(),
            'apply_url': str(raw.get('apply_url', '')).strip(),
            'source_url': str(raw.get('source_url', '')).strip(),
        }
    
    def _should_stop(self) -> bool:
        return len(self.jobs) >= self.max_jobs


class SeleniumCrawlerBase(JobCrawlerBase):
    """Selenium爬虫基类"""
    
    def __init__(self, max_jobs: int = MAX_JOBS_PER_COMPANY, headless: bool = True):
        super().__init__(max_jobs)
        self.headless = headless
        self.driver = None

    def _init_driver(self):
        """初始化Selenium驱动"""
        if not SELENIUM_AVAILABLE:
            raise RuntimeError("Selenium not installed")
            
        options = Options()
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # 绕过检测
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            logger.warning(f"无法使用webdriver-manager，尝试直接初始化: {e}")
            self.driver = webdriver.Chrome(options=options)
            
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
        self.driver.implicitly_wait(10)

    def _close_driver(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def crawl(self) -> List[Dict]:
        try:
            self._init_driver()
            return self._crawl_implementation()
        except Exception as e:
            logger.error(f"❌ {self.company_name} (Selenium) 失败: {e}")
            return []
        finally:
            self._close_driver()

    @abstractmethod
    def _crawl_implementation(self) -> List[Dict]:
        pass


# ==================== 具体的Selenium爬虫实现 ====================

class AlibabaSeleniumCrawler(SeleniumCrawlerBase):
    """阿里巴巴 Selenium 爬虫"""
    @property
    def company_name(self) -> str:
        return "阿里巴巴"

    def _crawl_implementation(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name} (Selenium)...")
        url = "https://talent.alibaba.com/off-campus/position-list?lang=zh"
        self.driver.get(url)
        time.sleep(5)
        
        page = 1
        while not self._should_stop():
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "list-content"))
                )
            except:
                break
                
            items = self.driver.find_elements(By.CSS_SELECTOR, ".list-item, .position-item, a[href*='/position-detail']")
            if not items:
                break
                
            for item in items:
                if self._should_stop(): break
                try:
                    title_ele = item.find_element(By.CSS_SELECTOR, ".title-text, .position-title")
                    title = title_ele.text
                    link = title_ele.get_attribute("href") or item.get_attribute("href")
                    
                    try:
                        loc_ele = item.find_elements(By.CSS_SELECTOR, ".position-location, .location")
                        location = loc_ele[0].text if loc_ele else ""
                    except:
                        location = ""
                    
                    self.jobs.append(self._normalize_job({
                        'job_title': title,
                        'job_id': link.split('=')[-1] if link else str(len(self.jobs)),
                        'location': location,
                        'apply_url': link,
                        'source_url': link,
                    }))
                except:
                    continue
            
            try:
                next_btn = self.driver.find_element(By.CSS_SELECTOR, ".pagination-next:not(.disabled), .btn-next:not([disabled])")
                next_btn.click()
                time.sleep(3)
                page += 1
            except:
                break
                
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class MeituanSeleniumCrawler(SeleniumCrawlerBase):
    """美团 Selenium 爬虫"""
    @property
    def company_name(self) -> str:
        return "美团"

    def _crawl_implementation(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name} (Selenium)...")
        url = "https://zhaopin.meituan.com/web/social"
        self.driver.get(url)
        time.sleep(5)
        
        while not self._should_stop():
            items = self.driver.find_elements(By.CSS_SELECTOR, ".position-card-container, .job-item, tr")
            if not items:
                break
                
            for item in items:
                if self._should_stop(): break
                try:
                    title = item.find_element(By.CSS_SELECTOR, ".position-title-text, .job-title, a").text
                    link_ele = item.find_element(By.TAG_NAME, "a")
                    link = link_ele.get_attribute("href")
                    
                    try:
                        loc = item.find_element(By.CSS_SELECTOR, ".position-work-city, .work-city").text
                    except:
                        loc = ""
                    
                    self.jobs.append(self._normalize_job({
                        'job_title': title,
                        'job_id': link.split('=')[-1] if link else str(len(self.jobs)),
                        'location': loc,
                        'apply_url': link,
                        'source_url': link,
                    }))
                except:
                    continue
            
            try:
                next_btn = self.driver.find_element(By.CSS_SELECTOR, ".pagination li:last-child:not(.disabled)")
                next_btn.click()
                time.sleep(3)
            except:
                break
                
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class JDSeleniumCrawler(SeleniumCrawlerBase):
    """京东 Selenium 爬虫"""
    @property
    def company_name(self) -> str:
        return "京东"

    def _crawl_implementation(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name} (Selenium)...")
        url = "https://zhaopin.jd.com/web/job/job_list?jobType=1"
        self.driver.get(url)
        time.sleep(5)
        
        while not self._should_stop():
            items = self.driver.find_elements(By.CSS_SELECTOR, ".job-card, .list-item, .job-list-item")
            if not items:
                break
                
            for item in items:
                if self._should_stop(): break
                try:
                    title = item.find_element(By.CSS_SELECTOR, ".job-name, .title, .job-title").text
                    link = item.get_attribute("href") or item.find_element(By.TAG_NAME, "a").get_attribute("href")
                    
                    self.jobs.append(self._normalize_job({
                        'job_title': title,
                        'job_id': str(len(self.jobs)),
                        'apply_url': link,
                        'source_url': link,
                    }))
                except:
                    continue
            
            try:
                next_btn = self.driver.find_element(By.CSS_SELECTOR, ".btn-next")
                next_btn.click()
                time.sleep(3)
            except:
                break
                
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


# ==================== 国内大厂 (API版) ====================

class TencentCrawler(JobCrawlerBase):
    """腾讯"""
    @property
    def company_name(self) -> str:
        return "腾讯"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        for job_type in ['social', 'campus']:
            if self._should_stop():
                break
            page = 1
            while not self._should_stop():
                url = "https://careers.tencent.com/tencentcareer/api/post/Query"
                params = {'timestamp': int(time.time()*1000), 'attrId': '1' if job_type=='campus' else '', 'pageIndex': page, 'pageSize': 50, 'language': 'zh-cn', 'area': 'cn'}
                resp = self._request(url, params=params)
                if not resp:
                    break
                try:
                    data = resp.json()
                    posts = data.get('Data', {}).get('Posts', [])
                    if not posts:
                        break
                    for post in posts:
                        if self._should_stop():
                            break
                        self.jobs.append(self._normalize_job({
                            'job_title': post.get('RecruitPostName', ''),
                            'job_id': f"TC_{post.get('PostId', '')}",
                            'category': '校招' if job_type=='campus' else '社招',
                            'location': post.get('LocationName', ''),
                            'job_type': post.get('CategoryName', ''),
                            'special_program': post.get('BGName', ''),
                            'job_description': post.get('Responsibility', ''),
                            'job_requirements': post.get('Requirement', ''),
                            'apply_url': f"https://careers.tencent.com/jobdesc.html?postId={post.get('PostId', '')}",
                        }))
                    if page * 50 >= data.get('Data', {}).get('Count', 0):
                        break
                    page += 1
                except:
                    break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class AlibabaCrawler(JobCrawlerBase):
    """阿里巴巴"""
    @property
    def company_name(self) -> str:
        return "阿里巴巴"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
            url = "https://talent.alibaba.com/off_campus/position/list"
            payload = {"pageSize": 50, "pageIndex": page, "language": "zh", "channel": "group_official_site"}
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
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': pos.get('name', ''),
                        'job_id': f"ALI_{pos.get('code', '')}",
                        'category': '校招' if pos.get('isSchool') else '社招',
                        'location': ', '.join(pos.get('workLocations', [])) if pos.get('workLocations') else '',
                        'job_type': pos.get('jobCategory', {}).get('name', '') if isinstance(pos.get('jobCategory'), dict) else '',
                        'special_program': pos.get('department', {}).get('name', '') if isinstance(pos.get('department'), dict) else '',
                        'job_description': pos.get('description', ''),
                        'job_requirements': pos.get('requirement', ''),
                        'apply_url': f"https://talent.alibaba.com/off-campus/position-detail?positionId={pos.get('code', '')}",
                    }))
                if page >= data.get('content', {}).get('data', {}).get('page', {}).get('totalPage', 0):
                    break
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class BaiduCrawler(JobCrawlerBase):
    """百度"""
    @property
    def company_name(self) -> str:
        return "百度"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        for recruit_type in ['SOCIAL', 'CAMPUS']:
            if self._should_stop():
                break
            page = 1
            while not self._should_stop():
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
                        if self._should_stop():
                            break
                        self.jobs.append(self._normalize_job({
                            'job_title': post.get('name', ''),
                            'job_id': f"BD_{post.get('postId', '')}",
                            'category': '校招' if recruit_type == 'CAMPUS' else '社招',
                            'location': post.get('workPlace', ''),
                            'job_type': post.get('serviceType', ''),
                            'job_description': post.get('serviceCondition', ''),
                            'job_requirements': post.get('workContent', ''),
                            'apply_url': f"https://talent.baidu.com/jobs/detail/{post.get('postId', '')}",
                        }))
                    if page * 50 >= data.get('data', {}).get('total', 0):
                        break
                    page += 1
                except:
                    break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class MeituanCrawler(JobCrawlerBase):
    """美团"""
    @property
    def company_name(self) -> str:
        return "美团"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        for job_type in [1, 2]:
            if self._should_stop():
                break
            offset = 0
            while not self._should_stop():
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
                        if self._should_stop():
                            break
                        self.jobs.append(self._normalize_job({
                            'job_title': job.get('name', ''),
                            'job_id': f"MT_{job.get('id', '')}",
                            'category': '校招' if job_type == 2 else '社招',
                            'location': job.get('city', ''),
                            'job_type': job.get('jobCategory', ''),
                            'special_program': job.get('orgName', ''),
                            'job_description': job.get('responsibility', ''),
                            'job_requirements': job.get('requirement', ''),
                            'apply_url': f"https://zhaopin.meituan.com/job-detail?jobId={job.get('id', '')}",
                        }))
                    if offset + 50 >= data.get('data', {}).get('total', 0):
                        break
                    offset += 50
                except:
                    break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class JDCrawler(JobCrawlerBase):
    """京东"""
    @property
    def company_name(self) -> str:
        return "京东"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
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
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('jobName', ''),
                        'job_id': f"JD_{job.get('jobId', '')}",
                        'category': '社招',
                        'location': job.get('workCity', ''),
                        'job_type': job.get('jobType', ''),
                        'special_program': job.get('deptName', ''),
                        'job_description': job.get('jobDesc', ''),
                        'job_requirements': job.get('jobRequire', ''),
                        'apply_url': f"https://zhaopin.jd.com/web/job/job_detail?jobId={job.get('jobId', '')}",
                    }))
                if page * 50 >= data.get('data', {}).get('total', 0):
                    break
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class NeteaseCrawler(JobCrawlerBase):
    """网易"""
    @property
    def company_name(self) -> str:
        return "网易"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
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
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': pos.get('name', ''),
                        'job_id': f"NE_{pos.get('id', '')}",
                        'category': pos.get('recruitTypeName', '社招'),
                        'location': pos.get('workPlaceName', ''),
                        'job_type': pos.get('firstPostTypeName', ''),
                        'special_program': pos.get('deptName', ''),
                        'job_description': pos.get('requirement', ''),
                        'apply_url': f"https://hr.163.com/position/detail.html?id={pos.get('id', '')}",
                    }))
                if page >= data.get('data', {}).get('pages', 0):
                    break
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class KuaishouCrawler(JobCrawlerBase):
    """快手"""
    @property
    def company_name(self) -> str:
        return "快手"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
            url = "https://zhaopin.kuaishou.cn/recruit/api/job/list"
            params = {'page': page, 'pageSize': 50}
            resp = self._request(url, params=params)
            if not resp:
                break
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('jobList', [])
                if not jobs:
                    break
                for job in jobs:
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('jobName', ''),
                        'job_id': f"KS_{job.get('jobId', '')}",
                        'category': job.get('jobType', '社招'),
                        'location': job.get('workCity', ''),
                        'job_type': job.get('jobCategory', ''),
                        'job_description': job.get('jobResponsibility', ''),
                        'job_requirements': job.get('jobRequirements', ''),
                        'apply_url': f"https://zhaopin.kuaishou.cn/recruit/e/#/official/jobs/detail/{job.get('jobId', '')}",
                    }))
                if page * 50 >= data.get('data', {}).get('total', 0):
                    break
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class XiaomiCrawler(JobCrawlerBase):
    """小米"""
    @property
    def company_name(self) -> str:
        return "小米"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
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
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('positionName', ''),
                        'job_id': f"XM_{job.get('id', '')}",
                        'category': job.get('recruitType', '社招'),
                        'location': job.get('workCity', ''),
                        'job_type': job.get('categoryName', ''),
                        'job_description': job.get('requirement', ''),
                        'job_requirements': job.get('description', ''),
                        'apply_url': f"https://hr.xiaomi.com/position/{job.get('id', '')}",
                    }))
                if page * 50 >= data.get('data', {}).get('total', 0):
                    break
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class BilibiliCrawler(JobCrawlerBase):
    """B站"""
    @property
    def company_name(self) -> str:
        return "哔哩哔哩"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
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
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('name', ''),
                        'job_id': f"BL_{job.get('id', '')}",
                        'category': job.get('type', '社招'),
                        'location': job.get('city', ''),
                        'job_type': job.get('category', ''),
                        'job_description': job.get('description', ''),
                        'job_requirements': job.get('requirement', ''),
                        'apply_url': f"https://jobs.bilibili.com/position/{job.get('id', '')}",
                    }))
                if page * 50 >= data.get('data', {}).get('total', 0):
                    break
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class DidiCrawler(JobCrawlerBase):
    """滴滴"""
    @property
    def company_name(self) -> str:
        return "滴滴"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
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
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('name', ''),
                        'job_id': f"DD_{job.get('id', '')}",
                        'category': job.get('recruitType', '社招'),
                        'location': job.get('city', ''),
                        'job_type': job.get('category', ''),
                        'job_description': job.get('description', ''),
                        'job_requirements': job.get('requirement', ''),
                        'apply_url': f"https://talent.didiglobal.com/position/{job.get('id', '')}",
                    }))
                if page * 50 >= data.get('data', {}).get('total', 0):
                    break
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class PinduoduoCrawler(JobCrawlerBase):
    """拼多多"""
    @property
    def company_name(self) -> str:
        return "拼多多"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
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
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('name', ''),
                        'job_id': f"PDD_{job.get('id', '')}",
                        'category': job.get('type', '社招'),
                        'location': job.get('city', ''),
                        'job_type': job.get('category', ''),
                        'job_description': job.get('description', ''),
                        'job_requirements': job.get('requirement', ''),
                        'apply_url': f"https://careers.pinduoduo.com/position/{job.get('id', '')}",
                    }))
                if page * 50 >= data.get('data', {}).get('total', 0):
                    break
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class HuaweiCrawler(JobCrawlerBase):
    """华为"""
    @property
    def company_name(self) -> str:
        return "华为"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
            url = "https://career.huawei.com/reccampportal/portal5/position/api/position/queryPositions"
            payload = {"pageIndex": page, "pageSize": 50}
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
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('positionName', ''),
                        'job_id': f"HW_{job.get('positionId', '')}",
                        'category': job.get('positionType', ''),
                        'location': job.get('workLocation', ''),
                        'job_type': job.get('jobType', ''),
                        'job_description': job.get('requirement', ''),
                        'job_requirements': job.get('description', ''),
                        'apply_url': f"https://career.huawei.com/reccampportal/campus/position/{job.get('positionId', '')}",
                    }))
                if page * 50 >= data.get('data', {}).get('total', 0):
                    break
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class ByteDanceCrawler(JobCrawlerBase):
    """字节跳动 - 从文件加载"""
    @property
    def company_name(self) -> str:
        return "字节跳动"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"📂 {self.company_name} (从文件加载)...")
        for fname in ['bytedance_jobs.json', 'bytedance_jobs copy.json']:
            fpath = ROOT_DIR / fname
            if fpath.exists():
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    for item in data[:self.max_jobs]:
                        self.jobs.append(self._normalize_job(item))
                    logger.info(f"  └─ {len(self.jobs)} 个")
                    return self.jobs
                except:
                    pass
        logger.warning(f"  └─ 未找到数据文件")
        return []


# ==================== 外企 ====================

class AmazonCrawler(JobCrawlerBase):
    """Amazon"""
    @property
    def company_name(self) -> str:
        return "Amazon"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        offset = 0
        while not self._should_stop():
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
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('title', ''),
                        'job_id': f"AMZ_{job.get('id_icims', '')}",
                        'category': job.get('job_category', ''),
                        'location': job.get('location', ''),
                        'job_type': job.get('primary_search_label', ''),
                        'special_program': job.get('business_category', ''),
                        'job_description': job.get('description_short', ''),
                        'job_requirements': job.get('basic_qualifications', ''),
                        'apply_url': f"https://www.amazon.jobs{job.get('job_path', '')}",
                    }))
                if offset + 100 >= data.get('hits', 0):
                    break
                offset += 100
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class MicrosoftCrawler(JobCrawlerBase):
    """Microsoft"""
    @property
    def company_name(self) -> str:
        return "Microsoft"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        skip = 0
        while not self._should_stop():
            url = "https://gcsservices.careers.microsoft.com/search/api/v1/search"
            params = {'l': 'zh_cn', 'pg': skip//100+1, 'pgSz': 100, 'o': skip, 'flt': 'true'}
            resp = self._request(url, params=params)
            if not resp:
                break
            try:
                data = resp.json()
                jobs = data.get('operationResult', {}).get('result', {}).get('jobs', [])
                if not jobs:
                    break
                for job in jobs:
                    if self._should_stop():
                        break
                    props = job.get('properties', {})
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('title', ''),
                        'job_id': f"MS_{job.get('jobId', '')}",
                        'category': props.get('employmentType', ''),
                        'location': ', '.join(props.get('locations', [])) if props.get('locations') else '',
                        'job_type': props.get('discipline', ''),
                        'job_description': job.get('description', ''),
                        'apply_url': f"https://jobs.careers.microsoft.com/global/en/job/{job.get('jobId', '')}",
                    }))
                total = data.get('operationResult', {}).get('result', {}).get('totalJobs', 0)
                if skip + 100 >= total:
                    break
                skip += 100
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class GoogleCrawler(JobCrawlerBase):
    """Google"""
    @property
    def company_name(self) -> str:
        return "Google"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page_token = ""
        while not self._should_stop():
            url = "https://careers.google.com/api/v3/search/"
            params = {'company': 'Google', 'hl': 'zh_CN', 'location': 'China', 'page_size': 100, 'q': ''}
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
                    if self._should_stop():
                        break
                    locs = [loc.get('display', '') for loc in job.get('locations', [])]
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('title', ''),
                        'job_id': f"GOOG_{job.get('id', '')}",
                        'category': 'Full-time',
                        'location': ', '.join(locs),
                        'job_type': ', '.join(job.get('categories', [])),
                        'job_description': job.get('description', ''),
                        'job_requirements': job.get('qualifications', ''),
                        'apply_url': f"https://careers.google.com/jobs/results/{job.get('id', '')}",
                    }))
                page_token = data.get('next_page_token', '')
                if not page_token:
                    break
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


# ==================== 新增公司 ====================

class CtripCrawler(JobCrawlerBase):
    """携程"""
    @property
    def company_name(self) -> str:
        return "携程"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
            url = "https://careers.ctrip.com/api/jobs"
            params = {'pageIndex': page, 'pageSize': 50}
            resp = self._request(url, params=params)
            if not resp:
                break
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('list', []) or data.get('jobs', [])
                if not jobs:
                    break
                for job in jobs:
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('jobName', job.get('title', '')),
                        'job_id': f"CTRIP_{job.get('jobId', job.get('id', ''))}",
                        'category': job.get('recruitType', '社招'),
                        'location': job.get('workCity', job.get('location', '')),
                        'job_type': job.get('category', ''),
                        'job_description': job.get('jobDesc', job.get('description', '')),
                        'apply_url': f"https://careers.ctrip.com/job/{job.get('jobId', job.get('id', ''))}",
                    }))
                page += 1
                if len(self.jobs) >= self.max_jobs:
                    break
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class DJICrawler(JobCrawlerBase):
    """大疆"""
    @property
    def company_name(self) -> str:
        return "大疆"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
            url = "https://we.dji.com/api/v1/jobs"
            params = {'page': page, 'size': 50, 'lang': 'zh-CN'}
            resp = self._request(url, params=params)
            if not resp:
                break
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('list', []) or data.get('list', [])
                if not jobs:
                    break
                for job in jobs:
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('name', job.get('title', '')),
                        'job_id': f"DJI_{job.get('id', '')}",
                        'category': job.get('type', '社招'),
                        'location': job.get('city', job.get('location', '')),
                        'job_type': job.get('category', ''),
                        'job_description': job.get('description', ''),
                        'apply_url': f"https://we.dji.com/zh-CN/position/{job.get('id', '')}",
                    }))
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class NIOCrawler(JobCrawlerBase):
    """蔚来"""
    @property
    def company_name(self) -> str:
        return "蔚来"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
            url = "https://nio.jobs.feishu.cn/api/v1/search/job"
            payload = {"offset": (page-1)*20, "limit": 20, "keyword": ""}
            headers = {**DEFAULT_HEADERS, 'Content-Type': 'application/json'}
            resp = self._request(url, method='POST', json=payload, headers=headers)
            if not resp:
                break
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('job_list', [])
                if not jobs:
                    break
                for job in jobs:
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('title', ''),
                        'job_id': f"NIO_{job.get('id', '')}",
                        'category': job.get('recruit_type', {}).get('name', ''),
                        'location': job.get('city', {}).get('name', ''),
                        'job_type': job.get('job_function', {}).get('name', ''),
                        'job_description': job.get('description', ''),
                        'apply_url': f"https://nio.jobs.feishu.cn/job/{job.get('id', '')}",
                    }))
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class XPengCrawler(JobCrawlerBase):
    """小鹏"""
    @property
    def company_name(self) -> str:
        return "小鹏"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
            url = "https://job.xiaopeng.com/api/job/list"
            params = {'page': page, 'size': 50}
            resp = self._request(url, params=params)
            if not resp:
                break
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('list', [])
                if not jobs:
                    break
                for job in jobs:
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('name', ''),
                        'job_id': f"XPENG_{job.get('id', '')}",
                        'category': job.get('type', ''),
                        'location': job.get('city', ''),
                        'job_type': job.get('category', ''),
                        'job_description': job.get('description', ''),
                        'apply_url': f"https://job.xiaopeng.com/job/{job.get('id', '')}",
                    }))
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class LiAutoCrawler(JobCrawlerBase):
    """理想"""
    @property
    def company_name(self) -> str:
        return "理想汽车"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
            url = "https://www.lixiang.com/api/job/list"
            params = {'page': page, 'size': 50}
            resp = self._request(url, params=params)
            if not resp:
                break
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('list', [])
                if not jobs:
                    break
                for job in jobs:
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('name', ''),
                        'job_id': f"LI_{job.get('id', '')}",
                        'category': job.get('type', ''),
                        'location': job.get('city', ''),
                        'job_type': job.get('category', ''),
                        'job_description': job.get('description', ''),
                        'apply_url': f"https://www.lixiang.com/job/{job.get('id', '')}",
                    }))
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class OPPOCrawler(JobCrawlerBase):
    """OPPO"""
    @property
    def company_name(self) -> str:
        return "OPPO"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
            url = "https://careers.oppo.com/campus/api/position/list"
            params = {'pageNo': page, 'pageSize': 50}
            resp = self._request(url, params=params)
            if not resp:
                break
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('list', []) or data.get('result', {}).get('list', [])
                if not jobs:
                    break
                for job in jobs:
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('positionName', job.get('name', '')),
                        'job_id': f"OPPO_{job.get('positionId', job.get('id', ''))}",
                        'category': job.get('recruitType', ''),
                        'location': job.get('workCity', job.get('city', '')),
                        'job_type': job.get('positionType', ''),
                        'job_description': job.get('positionDesc', job.get('description', '')),
                        'apply_url': f"https://careers.oppo.com/campus/position/{job.get('positionId', job.get('id', ''))}",
                    }))
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class VIVOCrawler(JobCrawlerBase):
    """VIVO"""
    @property
    def company_name(self) -> str:
        return "VIVO"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
            url = "https://hr.vivo.com/api/job/list"
            params = {'page': page, 'size': 50}
            resp = self._request(url, params=params)
            if not resp:
                break
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('list', [])
                if not jobs:
                    break
                for job in jobs:
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('name', ''),
                        'job_id': f"VIVO_{job.get('id', '')}",
                        'category': job.get('type', ''),
                        'location': job.get('city', ''),
                        'job_type': job.get('category', ''),
                        'job_description': job.get('description', ''),
                        'apply_url': f"https://hr.vivo.com/job/{job.get('id', '')}",
                    }))
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class SenseTimeCrawler(JobCrawlerBase):
    """商汤"""
    @property
    def company_name(self) -> str:
        return "商汤科技"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
            url = "https://hr.sensetime.com/api/job/list"
            params = {'page': page, 'size': 50}
            resp = self._request(url, params=params)
            if not resp:
                break
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('list', [])
                if not jobs:
                    break
                for job in jobs:
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('name', ''),
                        'job_id': f"ST_{job.get('id', '')}",
                        'category': job.get('type', ''),
                        'location': job.get('city', ''),
                        'job_type': job.get('category', ''),
                        'job_description': job.get('description', ''),
                        'apply_url': f"https://hr.sensetime.com/job/{job.get('id', '')}",
                    }))
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class ByteDanceAPICrawler(JobCrawlerBase):
    """字节跳动 - 尝试API"""
    @property
    def company_name(self) -> str:
        return "字节跳动"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name} (尝试API)...")
        # 尝试字节的API
        offset = 0
        while not self._should_stop():
            url = "https://jobs.bytedance.com/api/v1/search/job/posts"
            params = {'offset': offset, 'limit': 50, 'keyword': ''}
            resp = self._request(url, params=params)
            if not resp:
                # API失败，从文件加载
                return self._load_from_file()
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('job_post_list', [])
                if not jobs:
                    if not self.jobs:
                        return self._load_from_file()
                    break
                for job in jobs:
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('title', ''),
                        'job_id': job.get('id', ''),
                        'category': job.get('recruit_type', {}).get('name', ''),
                        'location': job.get('city', {}).get('name', ''),
                        'job_type': job.get('job_category', {}).get('name', ''),
                        'job_description': job.get('description', ''),
                        'job_requirements': job.get('requirement', ''),
                        'apply_url': f"https://jobs.bytedance.com/position/{job.get('id', '')}",
                    }))
                offset += 50
            except:
                if not self.jobs:
                    return self._load_from_file()
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs
    
    def _load_from_file(self) -> List[Dict]:
        """从文件加载"""
        for fname in ['bytedance_jobs.json', 'bytedance_jobs copy.json']:
            fpath = ROOT_DIR / fname
            if fpath.exists():
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    for item in data[:self.max_jobs]:
                        self.jobs.append(self._normalize_job(item))
                    logger.info(f"  └─ {len(self.jobs)} 个 (从文件)")
                    return self.jobs
                except:
                    pass
        logger.warning(f"  └─ 0 个")
        return []


# ==================== 招聘平台 ====================

class LagouCrawler(JobCrawlerBase):
    """拉勾网 - 多家公司"""
    @property
    def company_name(self) -> str:
        return "拉勾网"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        # 尝试不同的API端点
        endpoints = [
            "https://www.lagou.com/wn/zhaopin",
            "https://a.]lagou.com/position/positionAjax.json",
        ]
        while not self._should_stop():
            url = "https://www.lagou.com/wn/jobs"
            params = {'pn': page, 'kd': '', 'city': '全国'}
            resp = self._request(url, params=params)
            if not resp:
                break
            try:
                data = resp.json()
                jobs = data.get('content', {}).get('positionResult', {}).get('result', [])
                if not jobs:
                    break
                for job in jobs:
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('positionName', ''),
                        'job_id': f"LG_{job.get('positionId', '')}",
                        'category': job.get('education', ''),
                        'location': job.get('city', ''),
                        'job_type': job.get('industryField', ''),
                        'special_program': job.get('companyFullName', ''),
                        'job_description': job.get('positionAdvantage', ''),
                        'apply_url': f"https://www.lagou.com/wn/jobs/{job.get('positionId', '')}",
                    }))
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class ZhilianCrawler(JobCrawlerBase):
    """智联招聘"""
    @property
    def company_name(self) -> str:
        return "智联招聘"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
            url = "https://fe-api.zhaopin.com/c/i/sou"
            params = {'start': (page-1)*90, 'pageSize': 90, 'cityId': '489', 'kw': ''}
            headers = {**DEFAULT_HEADERS, 'Referer': 'https://sou.zhaopin.com/'}
            resp = self._request(url, params=params, headers=headers)
            if not resp:
                break
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('results', [])
                if not jobs:
                    break
                for job in jobs:
                    if self._should_stop():
                        break
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('jobName', ''),
                        'job_id': f"ZL_{job.get('number', '')}",
                        'category': job.get('eduLevel', {}).get('name', ''),
                        'location': job.get('city', {}).get('display', ''),
                        'job_type': job.get('jobType', {}).get('name', ''),
                        'special_program': job.get('company', {}).get('name', ''),
                        'job_description': job.get('welfare', ''),
                        'apply_url': job.get('positionURL', ''),
                    }))
                page += 1
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


class Job51Crawler(JobCrawlerBase):
    """前程无忧"""
    @property
    def company_name(self) -> str:
        return "前程无忧"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        page = 1
        while not self._should_stop():
            url = "https://search.51job.com/list/010000,000000,0000,00,9,99,+,2,{}.html".format(page)
            resp = self._request(url)
            if not resp:
                break
            # 51job返回HTML，这里暂时跳过
            break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


# 尝试使用飞书招聘API获取多家公司数据
class FeishuJobsCrawler(JobCrawlerBase):
    """飞书招聘 - 多家公司"""
    def __init__(self, company_code: str, company_name: str, max_jobs: int = MAX_JOBS_PER_COMPANY):
        super().__init__(max_jobs)
        self._company_code = company_code
        self._company_name = company_name
    
    @property
    def company_name(self) -> str:
        return self._company_name
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name}...")
        offset = 0
        while not self._should_stop():
            url = f"https://{self._company_code}.jobs.feishu.cn/api/v1/search/job"
            payload = {"offset": offset, "limit": 20, "keyword": ""}
            headers = {**DEFAULT_HEADERS, 'Content-Type': 'application/json'}
            resp = self._request(url, method='POST', json=payload, headers=headers)
            if not resp:
                break
            try:
                data = resp.json()
                jobs = data.get('data', {}).get('job_list', [])
                if not jobs:
                    break
                for job in jobs:
                    if self._should_stop():
                        break
                    city = job.get('city', {})
                    city_name = city.get('name', '') if isinstance(city, dict) else str(city)
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('title', ''),
                        'job_id': f"{self._company_code}_{job.get('id', '')}",
                        'category': job.get('recruit_type', {}).get('name', '') if isinstance(job.get('recruit_type'), dict) else '',
                        'location': city_name,
                        'job_type': job.get('job_function', {}).get('name', '') if isinstance(job.get('job_function'), dict) else '',
                        'job_description': job.get('description', ''),
                        'apply_url': f"https://{self._company_code}.jobs.feishu.cn/job/{job.get('id', '')}",
                    }))
                offset += 20
            except:
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


# 飞书招聘公司列表
def create_feishu_crawler(company_code: str, company_name: str):
    class SpecificFeishuCrawler(FeishuJobsCrawler):
        def __init__(self, max_jobs=MAX_JOBS_PER_COMPANY):
            super().__init__(company_code, company_name, max_jobs)
    return SpecificFeishuCrawler


# ==================== 爬虫注册表 ====================

CRAWLERS = {
    # 国内大厂 - 已验证可用 (API)
    'tencent': TencentCrawler,
    'netease': NeteaseCrawler,
    'bytedance': ByteDanceAPICrawler,
    # 国内大厂 - Selenium版 (增强抗反爬)
    'alibaba': AlibabaSeleniumCrawler,
    'meituan': MeituanSeleniumCrawler,
    'jd': JDSeleniumCrawler,
    # 其他国内大厂 (API)
    'baidu': BaiduCrawler,
    'kuaishou': KuaishouCrawler,
    'xiaomi': XiaomiCrawler,
    'bilibili': BilibiliCrawler,
    'didi': DidiCrawler,
    'pinduoduo': PinduoduoCrawler,
    'huawei': HuaweiCrawler,
    # 新增公司
    'ctrip': CtripCrawler,
    'dji': DJICrawler,
    'nio': NIOCrawler,
    'xpeng': XPengCrawler,
    'li': LiAutoCrawler,
    'oppo': OPPOCrawler,
    'vivo': VIVOCrawler,
    'sensetime': SenseTimeCrawler,
    # 飞书招聘平台公司
    'mihoyo': create_feishu_crawler('mihoyo', '米哈游'),
    'shein': create_feishu_crawler('shein', 'SHEIN'),
    'shopee': create_feishu_crawler('shopee', 'Shopee'),
    'ke': create_feishu_crawler('ke', '贝壳找房'),
    'yuanfudao': create_feishu_crawler('yuanfudao', '猿辅导'),
    'zuoyebang': create_feishu_crawler('zuoyebang', '作业帮'),
    # 招聘平台
    'zhilian': ZhilianCrawler,
    'lagou': LagouCrawler,
    # 外企
    'amazon': AmazonCrawler,
    'microsoft': MicrosoftCrawler,
    'google': GoogleCrawler,
}

NAMES = {
    'tencent': '腾讯', 'alibaba': '阿里巴巴', 'baidu': '百度', 'meituan': '美团',
    'jd': '京东', 'netease': '网易', 'kuaishou': '快手', 'xiaomi': '小米',
    'bilibili': '哔哩哔哩', 'didi': '滴滴', 'pinduoduo': '拼多多', 'huawei': '华为',
    'bytedance': '字节跳动', 'ctrip': '携程', 'dji': '大疆', 'nio': '蔚来',
    'xpeng': '小鹏', 'li': '理想汽车', 'oppo': 'OPPO', 'vivo': 'VIVO',
    'sensetime': '商汤科技', 'mihoyo': '米哈游', 'shein': 'SHEIN', 'shopee': 'Shopee',
    'ke': '贝壳找房', 'yuanfudao': '猿辅导', 'zuoyebang': '作业帮',
    'zhilian': '智联招聘', 'lagou': '拉勾网',
    'amazon': 'Amazon', 'microsoft': 'Microsoft', 'google': 'Google',
}


def run_crawlers(companies: List[str], output_file: str, max_jobs: int = MAX_JOBS_PER_COMPANY):
    """运行爬虫"""
    all_jobs = []
    stats = {}
    
    logger.info(f"\n{'='*60}")
    logger.info(f"📥 爬取 {len(companies)} 家公司，每家最多 {max_jobs} 个岗位")
    logger.info(f"{'='*60}\n")
    
    for key in companies:
        if key not in CRAWLERS:
            logger.warning(f"⚠️  未知公司: {key}")
            continue
        try:
            crawler = CRAWLERS[key](max_jobs=max_jobs)
            jobs = crawler.crawl()
            if jobs:
                all_jobs.extend(jobs)
                stats[crawler.company_name] = len(jobs)
        except Exception as e:
            logger.error(f"❌ {NAMES.get(key, key)} 失败: {e}")
    
    # 去重
    seen = set()
    unique = []
    for job in all_jobs:
        k = f"{job['company_name']}_{job['job_id']}"
        if k not in seen:
            seen.add(k)
            unique.append(job)
    
    # 保存
    out = ROOT_DIR / output_file
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ 完成！共 {len(unique)} 个岗位")
    logger.info(f"{'='*60}")
    logger.info(f"📁 保存到: {output_file}")
    
    if stats:
        logger.info(f"\n📊 统计:")
        for company, count in sorted(stats.items(), key=lambda x: -x[1]):
            logger.info(f"  {company:12}: {count:4} 个")
    
    return unique


def main():
    parser = argparse.ArgumentParser(description='招聘信息爬虫 v2')
    parser.add_argument('-c', '--companies', nargs='*', default=None, help='公司列表')
    parser.add_argument('-f', '--file', default='crawled_jobs_raw.json', help='输出文件')
    parser.add_argument('-m', '--max', type=int, default=MAX_JOBS_PER_COMPANY, help='每家最大岗位数')
    parser.add_argument('--list', action='store_true', help='列出支持的公司')
    args = parser.parse_args()
    
    if args.list:
        print("\n支持的公司:")
        for k, v in NAMES.items():
            print(f"  {k:12} -> {v}")
        print(f"\n使用: python job_crawler_v2.py -c tencent netease amazon")
        return
    
    companies = args.companies or list(CRAWLERS.keys())
    run_crawlers(companies, args.file, args.max)


if __name__ == '__main__':
    main()
