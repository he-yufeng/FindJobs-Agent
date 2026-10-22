#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多公司招聘信息爬虫 v2
每家公司限制300个岗位，支持更多公司
"""

import argparse
import base64
import hashlib
import html
import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Dict, List, Optional
from abc import ABC, abstractmethod

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent

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

    #: True when the source lists postings newest-first, so a page whose
    #: items are all already-seen means nothing new is coming on later pages.
    #: Only enable after verifying the ordering against the live source.
    ORDERS_NEWEST_FIRST = False

    def __init__(self, max_jobs: int = MAX_JOBS_PER_COMPANY):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.jobs: List[Dict] = []
        self.max_jobs = max_jobs
        self._seen_keys: set = set()

    def set_seen(self, job_keys: set) -> None:
        """Hand the crawler the ledger of already-fetched job keys. Sources
        with ORDERS_NEWEST_FIRST use it to stop pagination early; every
        source still gets filtered again in the pipeline."""
        self._seen_keys = set(job_keys)

    def _all_seen(self, job_ids: List[str]) -> bool:
        """True when every id on the current page is already in the ledger."""
        return bool(self._seen_keys) and bool(job_ids) and all(
            f"{self.company_name}|{jid}" in self._seen_keys for jid in job_ids
        )

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

    # careers.tencent.com Query API returns postings newest-first by
    # LastUpdateTime (verified against the live endpoint 2026-10-22), so a
    # page with nothing new means later pages have nothing new either.
    ORDERS_NEWEST_FIRST = True

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
                    if self.ORDERS_NEWEST_FIRST and self._all_seen(
                        [f"TC_{post.get('PostId', '')}" for post in posts]
                    ):
                        logger.info(f"  └─ 第 {page} 页全部是已见岗位，增量模式提前停")
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


class ByteDanceAPICrawler(JobCrawlerBase):
    """字节跳动 - 尝试API"""
    @property
    def company_name(self) -> str:
        return "字节跳动"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name} (公开职位 API)...")
        # 字节招聘官网的公开职位 API（POST 分页）；旧 GET 形式已失效
        offset = 0
        while not self._should_stop():
            url = "https://jobs.bytedance.com/api/v1/search/job/posts"
            payload = {
                "keyword": "",
                "limit": 50,
                "offset": offset,
                "job_category_id_list": [],
                "location_code_list": [],
                "subject_id_list": [],
                "recruitment_id_list": [],
                "portal_type": 2,
                "job_function_id_list": [],
                "portal_entrance": 1,
            }
            try:
                resp = requests.post(
                    url, json=payload, headers=self._headers(), timeout=20, verify=False
                )
                data = resp.json()
            except Exception as e:
                logger.warning(f"  API 调用失败（{e}），停止本轮")
                break
            jobs = data.get('data', {}).get('job_post_list', [])
            if not jobs:
                break
            for job in jobs:
                if self._should_stop():
                    break
                city = job.get('city_info', {}) or {}
                self.jobs.append(self._normalize_job({
                    'job_title': job.get('title', ''),
                    'job_id': f"BD_{job.get('id', '')}",
                    'category': job.get('recruit_type', {}).get('name', ''),
                    'location': city.get('name', '') or job.get('city', {}).get('name', ''),
                    'job_type': job.get('job_category', {}).get('name', ''),
                    'job_description': job.get('description', ''),
                    'job_requirements': job.get('requirement', ''),
                    'apply_url': f"https://jobs.bytedance.com/position/{job.get('id', '')}",
                }))
            offset += 50
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs
    
    def _headers(self) -> Dict[str, str]:
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
            'Content-Type': 'application/json',
        }


# ==================== Moka ATS 通用 ====================

class MokaCrawler(JobCrawlerBase):
    """Moka (mokahr) 托管招聘站的通用爬虫。

    带会话 cookie 过阿里云 WAF 拿到站点页，从 init-data 里解析 aesIv；职位
    列表走 POST /api/outer/ats-apply/website/jobs/v2，响应体是 AES-CBC 加密
    （key 是响应里的 necromancer，iv 就是 aesIv），解密后按统一 schema 归一化。
    不同公司只是 host / channel / org / site_id 不同。
    """

    def __init__(self, host: str, channel: str, org: str, site_id: str,
                 company_name: str, max_jobs: int = MAX_JOBS_PER_COMPANY):
        super().__init__(max_jobs)
        self._host = host
        self._channel = channel
        self._org = org
        self._site_id = site_id
        self._company_name = company_name

    @property
    def company_name(self) -> str:
        return self._company_name

    @property
    def site_url(self) -> str:
        return f"https://{self._host}/{self._channel}/{self._org}/{self._site_id}"

    def _get_aes_iv(self) -> Optional[str]:
        # 首次请求通常只拿到阿里云 WAF 的 acw_tc cookie 和一个近乎空的页面，
        # 带 cookie 再请求一次才是完整站点页
        for _ in range(2):
            resp = self._request(self.site_url)
            if not resp or 'init-data' not in resp.text:
                continue
            m = re.search(r'id="init-data"[^>]*value="(.*?)"', resp.text, re.S)
            if not m:
                continue
            try:
                data = json.loads(html.unescape(m.group(1)))
            except ValueError:
                continue
            iv = data.get('aesIv')
            if iv:
                return iv
        return None

    @staticmethod
    def _decrypt(payload: Dict, iv: str) -> Dict:
        try:
            from Crypto.Cipher import AES
        except ImportError as e:
            raise RuntimeError("Moka 适配器需要 pycryptodome: pip install pycryptodome") from e
        ct = base64.b64decode(payload['data'])
        pt = AES.new(payload['necromancer'].encode(), AES.MODE_CBC, iv.encode()).decrypt(ct)
        return json.loads(pt[:-pt[-1]].decode('utf-8'))

    def crawl(self) -> List[Dict]:
        logger.info(f"🚀 {self.company_name} (Moka)...")
        iv = self._get_aes_iv()
        if not iv:
            logger.warning(f"  {self.company_name}: 拿不到 aesIv，站点结构可能变了")
            return self.jobs
        page = 1
        while not self._should_stop():
            url = f"https://{self._host}/api/outer/ats-apply/website/jobs/v2"
            payload = {
                "orgId": self._org, "siteId": self._site_id,
                "pageNo": page, "pageSize": 50,
                "locale": "zh-CN", "needStat": True,
            }
            headers = {**DEFAULT_HEADERS, 'Content-Type': 'application/json', 'Referer': self.site_url}
            resp = self._request(url, method='POST', json=payload, headers=headers)
            if not resp:
                break
            try:
                body = resp.json()
                data = self._decrypt(body, iv) if 'necromancer' in body else body
                jobs = data.get('data', {}).get('jobs', [])
                if not jobs:
                    break
                for job in jobs:
                    if self._should_stop():
                        break
                    locations = job.get('locations') or []
                    city = ' / '.join(dict.fromkeys(
                        loc.get('cityName', '') for loc in locations if loc.get('cityName')
                    ))
                    self.jobs.append(self._normalize_job({
                        'job_title': job.get('title', ''),
                        'job_id': f"{self._org}_{job.get('id', '')}",
                        'category': '校招' if 'campus' in self._channel else '社招',
                        'location': city,
                        'job_description': _strip_html(job.get('jobDescription', '')),
                        'apply_url': f"{self.site_url}#/job/{job.get('id', '')}",
                    }))
                total = data.get('data', {}).get('jobStats', {}).get('total', 0)
                if page * 50 >= total:
                    break
                page += 1
            except (ValueError, KeyError, RuntimeError) as e:
                logger.warning(f"  {self.company_name}: 解析失败（{e}）")
                break
        logger.info(f"  └─ {len(self.jobs)} 个")
        return self.jobs


def _strip_html(text: str) -> str:
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'</p>\s*<p[^>]*>', '\n', text)
    return re.sub(r'<[^>]+>', '', text).replace('&nbsp;', ' ').strip()


class DJICrawler(MokaCrawler):
    """大疆：社招在 Moka（we.dji.com 的旧接口已下线）"""
    def __init__(self, max_jobs: int = MAX_JOBS_PER_COMPANY):
        super().__init__('apply.careers.dji.com', 'social-recruitment',
                         'dji', '170070', '大疆', max_jobs)


class CtripCrawler(MokaCrawler):
    """携程：校招在 Moka（careers.ctrip.com 的自研接口已下线）"""
    def __init__(self, max_jobs: int = MAX_JOBS_PER_COMPANY):
        super().__init__('app.mokahr.com', 'campus-recruitment',
                         'trip', '117988', '携程', max_jobs)


# ==================== 爬虫注册表 ====================
# 2026-10-13 全量实测（scripts/verify_crawlers_v2.py）：只保留当时能返回岗位的
# 适配器。实测不通过的旧适配器已移出，代码留在 git 历史里备修复参考；要复活
# 某家，先跑 verify 脚本摸清接口现状再改。

CRAWLERS = {
    # API 适配器 - 2026-10-13 实测可用
    'tencent': TencentCrawler,
    'netease': NeteaseCrawler,
    'bytedance': ByteDanceAPICrawler,
    'amazon': AmazonCrawler,
    # Moka ATS - 同日实测可用
    'dji': DJICrawler,
    'ctrip': CtripCrawler,
    # Selenium 版 - 需要本机 Chrome，自动验证不覆盖
    'alibaba': AlibabaSeleniumCrawler,
    'meituan': MeituanSeleniumCrawler,
    'jd': JDSeleniumCrawler,
}

NAMES = {
    'tencent': '腾讯', 'netease': '网易', 'bytedance': '字节跳动', 'amazon': 'Amazon',
    'dji': '大疆', 'ctrip': '携程',
    'alibaba': '阿里巴巴', 'meituan': '美团', 'jd': '京东',
}


def run_crawlers(companies: List[str], output_file: str, max_jobs: int = MAX_JOBS_PER_COMPANY, seen_keys: Optional[set] = None):
    """运行爬虫

    seen_keys 是跨运行的已见岗位账本（`公司|job_id` 字符串）。声明了
    ORDERS_NEWEST_FIRST 的爬虫拿它提前停页；其余爬虫忽略它，增量过滤
    仍由 pipeline 在 fetch 之后统一做。
    """
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
            if seen_keys:
                crawler.set_seen(seen_keys)
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
        logger.info("\n📊 统计:")
        for company, count in sorted(stats.items(), key=lambda x: -x[1]):
            logger.info(f"  {company:12}: {count:4} 个")
    
    return unique


def main():
    parser = argparse.ArgumentParser(description='招聘信息爬虫 v2')
    parser.add_argument('-c', '--companies', nargs='*', default=None, help='公司列表')
    parser.add_argument('-f', '--file', default='crawled_jobs_raw.json', help='输出文件')
    parser.add_argument('-m', '--max', type=int, default=MAX_JOBS_PER_COMPANY, help='每家最大岗位数')
    parser.add_argument('--list', action='store_true', help='列出支持的公司')
    parser.add_argument('--seen-file', default=None, help='已见岗位账本 JSON（`公司|job_id` 字符串列表），支持早停的爬虫会用到')
    args = parser.parse_args()

    if args.list:
        print("\n支持的公司:")
        for k, v in NAMES.items():
            print(f"  {k:12} -> {v}")
        print("\n使用: python job_crawler_v2.py -c tencent netease amazon")
        return

    seen_keys = None
    if args.seen_file:
        try:
            with open(args.seen_file, 'r', encoding='utf-8') as fh:
                seen_keys = set(json.load(fh))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"已见账本读取失败，按全量爬: {exc}")
    companies = args.companies or list(CRAWLERS.keys())
    run_crawlers(companies, args.file, args.max, seen_keys=seen_keys)


if __name__ == '__main__':
    main()
