#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多公司招聘信息爬虫 - Selenium版本
使用浏览器自动化绕过反爬机制
支持：字节跳动、腾讯、阿里巴巴、百度、美团等
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

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.warning("Selenium未安装，请运行: pip install selenium webdriver-manager")


class SeleniumCrawlerBase(ABC):
    """Selenium爬虫基类"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None
        self.jobs: List[Dict] = []
    
    @property
    @abstractmethod
    def company_name(self) -> str:
        pass
    
    @abstractmethod
    def crawl(self) -> List[Dict]:
        pass
    
    def _init_driver(self):
        """初始化浏览器"""
        if not SELENIUM_AVAILABLE:
            raise RuntimeError("Selenium未安装")
        
        options = Options()
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        
        try:
            # 尝试使用webdriver-manager自动管理driver
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        except:
            # 回退到系统Chrome
            self.driver = webdriver.Chrome(options=options)
        
        self.driver.implicitly_wait(10)
        return self.driver
    
    def _close_driver(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def _normalize_job(self, raw: Dict) -> Dict:
        """标准化岗位数据格式"""
        return {
            'company_name': self.company_name,
            'job_title': raw.get('job_title', ''),
            'job_id': str(raw.get('job_id', '')),
            'category': raw.get('category', ''),
            'location': raw.get('location', ''),
            'job_type': raw.get('job_type', ''),
            'special_program': raw.get('special_program', ''),
            'job_description': raw.get('job_description', ''),
            'job_requirements': raw.get('job_requirements', ''),
            'apply_url': raw.get('apply_url', ''),
            'source_url': raw.get('source_url', ''),
        }
    
    def _random_sleep(self, min_s: float = 1, max_s: float = 3):
        """随机延迟"""
        time.sleep(random.uniform(min_s, max_s))


class ByteDanceSeleniumCrawler(SeleniumCrawlerBase):
    """字节跳动Selenium爬虫"""
    
    @property
    def company_name(self) -> str:
        return "字节跳动"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name} 招聘信息...")
        
        try:
            self._init_driver()
            
            # 爬取校招
            logger.info("  爬取校招...")
            campus_jobs = self._crawl_jobs('campus')
            self.jobs.extend(campus_jobs)
            logger.info(f"  校招获取 {len(campus_jobs)} 个岗位")
            
            # 爬取社招
            logger.info("  爬取社招...")
            social_jobs = self._crawl_jobs('experienced')
            self.jobs.extend(social_jobs)
            logger.info(f"  社招获取 {len(social_jobs)} 个岗位")
            
        except Exception as e:
            logger.error(f"爬取字节跳动失败: {e}")
        finally:
            self._close_driver()
        
        return self.jobs
    
    def _crawl_jobs(self, recruit_type: str) -> List[Dict]:
        """爬取指定类型的岗位"""
        jobs = []
        category = '校招' if recruit_type == 'campus' else '社招'
        
        base_url = f"https://jobs.bytedance.com/{recruit_type}/position"
        self.driver.get(base_url)
        self._random_sleep(2, 4)
        
        page = 1
        max_pages = 50  # 限制最大页数
        
        while page <= max_pages:
            try:
                # 等待岗位列表加载
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".position-card, .job-card, [class*='position']"))
                )
                
                # 获取页面数据 - 尝试从页面脚本获取JSON数据
                try:
                    # 方法1: 从window.__NEXT_DATA__获取
                    script = self.driver.execute_script(
                        "return window.__NEXT_DATA__ ? JSON.stringify(window.__NEXT_DATA__) : null"
                    )
                    if script:
                        data = json.loads(script)
                        job_list = self._extract_jobs_from_next_data(data, category)
                        if job_list:
                            jobs.extend(job_list)
                except:
                    pass
                
                # 方法2: 直接解析DOM
                if not jobs or page > 1:
                    job_cards = self.driver.find_elements(By.CSS_SELECTOR, ".position-card, .job-card, [class*='JobCard']")
                    for card in job_cards:
                        try:
                            job = self._parse_job_card(card, category)
                            if job and job.get('job_id') not in [j.get('job_id') for j in jobs]:
                                jobs.append(job)
                        except Exception as e:
                            continue
                
                # 尝试点击下一页
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, ".pagination-next, [class*='next'], button[aria-label='Next']")
                    if 'disabled' in next_btn.get_attribute('class') or not next_btn.is_enabled():
                        break
                    next_btn.click()
                    self._random_sleep(1, 2)
                    page += 1
                except NoSuchElementException:
                    break
                
            except TimeoutException:
                logger.warning(f"页面加载超时: page {page}")
                break
            except Exception as e:
                logger.warning(f"爬取第{page}页失败: {e}")
                break
        
        return jobs
    
    def _extract_jobs_from_next_data(self, data: Dict, category: str) -> List[Dict]:
        """从Next.js数据中提取岗位"""
        jobs = []
        try:
            # 尝试多种可能的数据路径
            props = data.get('props', {}).get('pageProps', {})
            job_list = props.get('jobList', []) or props.get('positions', []) or props.get('data', {}).get('job_post_list', [])
            
            for job in job_list:
                normalized = self._normalize_job({
                    'job_title': job.get('title', '') or job.get('name', ''),
                    'job_id': job.get('id', '') or job.get('job_id', ''),
                    'category': category,
                    'location': job.get('city', '') or job.get('location', ''),
                    'job_type': job.get('job_category', {}).get('name', '') if isinstance(job.get('job_category'), dict) else job.get('category', ''),
                    'special_program': job.get('subject', {}).get('name', '') if isinstance(job.get('subject'), dict) else '',
                    'job_description': job.get('description', ''),
                    'job_requirements': job.get('requirement', ''),
                    'apply_url': f"https://jobs.bytedance.com/position/{job.get('id', '')}/detail",
                    'source_url': f"https://jobs.bytedance.com/position/{job.get('id', '')}/detail",
                })
                jobs.append(normalized)
        except Exception as e:
            logger.debug(f"提取Next.js数据失败: {e}")
        return jobs
    
    def _parse_job_card(self, card, category: str) -> Optional[Dict]:
        """解析岗位卡片"""
        try:
            title_elem = card.find_element(By.CSS_SELECTOR, ".position-name, .job-title, h3, [class*='title']")
            title = title_elem.text.strip()
            
            # 获取链接
            try:
                link = card.find_element(By.TAG_NAME, 'a').get_attribute('href')
                job_id = re.search(r'/(\d+)', link).group(1) if link else ''
            except:
                link = ''
                job_id = ''
            
            # 获取地点
            try:
                location = card.find_element(By.CSS_SELECTOR, ".city, .location, [class*='city']").text.strip()
            except:
                location = ''
            
            # 获取类型
            try:
                job_type = card.find_element(By.CSS_SELECTOR, ".category, .type, [class*='category']").text.strip()
            except:
                job_type = ''
            
            return self._normalize_job({
                'job_title': title,
                'job_id': job_id,
                'category': category,
                'location': location,
                'job_type': job_type,
                'apply_url': link,
                'source_url': link,
            })
        except Exception as e:
            return None


class TencentSeleniumCrawler(SeleniumCrawlerBase):
    """腾讯Selenium爬虫"""
    
    @property
    def company_name(self) -> str:
        return "腾讯"
    
    def crawl(self) -> List[Dict]:
        logger.info(f"开始爬取 {self.company_name} 招聘信息...")
        
        try:
            self._init_driver()
            
            # 社招
            logger.info("  爬取社招...")
            social_jobs = self._crawl_social()
            self.jobs.extend(social_jobs)
            logger.info(f"  社招获取 {len(social_jobs)} 个岗位")
            
            # 校招
            logger.info("  爬取校招...")
            campus_jobs = self._crawl_campus()
            self.jobs.extend(campus_jobs)
            logger.info(f"  校招获取 {len(campus_jobs)} 个岗位")
            
        except Exception as e:
            logger.error(f"爬取腾讯失败: {e}")
        finally:
            self._close_driver()
        
        return self.jobs
    
    def _crawl_social(self) -> List[Dict]:
        """爬取社招"""
        jobs = []
        url = "https://careers.tencent.com/search.html"
        self.driver.get(url)
        self._random_sleep(3, 5)
        
        page = 1
        max_pages = 100
        
        while page <= max_pages:
            try:
                # 等待岗位加载
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".recruit-list, .job-list, [class*='recruit']"))
                )
                
                # 解析岗位
                cards = self.driver.find_elements(By.CSS_SELECTOR, ".recruit-list .recruit-item, .job-item")
                for card in cards:
                    job = self._parse_social_card(card)
                    if job:
                        jobs.append(job)
                
                logger.info(f"    第{page}页: 已获取 {len(jobs)} 个岗位")
                
                # 下一页
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, ".page-next:not(.disabled), .pagination-next")
                    if not next_btn.is_enabled():
                        break
                    next_btn.click()
                    self._random_sleep(1, 2)
                    page += 1
                except:
                    break
                    
            except TimeoutException:
                break
            except Exception as e:
                logger.warning(f"爬取社招第{page}页失败: {e}")
                break
        
        return jobs
    
    def _crawl_campus(self) -> List[Dict]:
        """爬取校招"""
        jobs = []
        url = "https://join.qq.com/post.html"
        self.driver.get(url)
        self._random_sleep(3, 5)
        
        page = 1
        max_pages = 50
        
        while page <= max_pages:
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".recruit-list, .position-list, [class*='job']"))
                )
                
                cards = self.driver.find_elements(By.CSS_SELECTOR, ".recruit-item, .position-item, .job-item")
                for card in cards:
                    job = self._parse_campus_card(card)
                    if job:
                        jobs.append(job)
                
                # 下一页
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, ".page-next:not(.disabled)")
                    if not next_btn.is_enabled():
                        break
                    next_btn.click()
                    self._random_sleep(1, 2)
                    page += 1
                except:
                    break
                    
            except:
                break
        
        return jobs
    
    def _parse_social_card(self, card) -> Optional[Dict]:
        """解析社招卡片"""
        try:
            title = card.find_element(By.CSS_SELECTOR, ".recruit-title, .job-title, h4").text.strip()
            
            try:
                link = card.find_element(By.TAG_NAME, 'a').get_attribute('href')
                job_id = re.search(r'postId=(\d+)', link).group(1) if link else ''
            except:
                link = ''
                job_id = ''
            
            try:
                location = card.find_element(By.CSS_SELECTOR, ".recruit-location, .location").text.strip()
            except:
                location = ''
            
            try:
                dept = card.find_element(By.CSS_SELECTOR, ".recruit-bg, .department").text.strip()
            except:
                dept = ''
            
            return self._normalize_job({
                'job_title': title,
                'job_id': job_id,
                'category': '社招',
                'location': location,
                'special_program': dept,
                'apply_url': link or f"https://careers.tencent.com/jobdesc.html?postId={job_id}",
                'source_url': link or f"https://careers.tencent.com/jobdesc.html?postId={job_id}",
            })
        except:
            return None
    
    def _parse_campus_card(self, card) -> Optional[Dict]:
        """解析校招卡片"""
        try:
            title = card.find_element(By.CSS_SELECTOR, ".recruit-title, .job-title, h4").text.strip()
            
            try:
                link = card.find_element(By.TAG_NAME, 'a').get_attribute('href')
                job_id = re.search(r'pid=(\d+)', link).group(1) if link else ''
            except:
                link = ''
                job_id = ''
            
            return self._normalize_job({
                'job_title': title,
                'job_id': job_id,
                'category': '校招',
                'apply_url': link or f"https://join.qq.com/post.html?pid={job_id}",
                'source_url': link or f"https://join.qq.com/post.html?pid={job_id}",
            })
        except:
            return None


# Selenium爬虫注册表
SELENIUM_CRAWLER_REGISTRY = {
    'bytedance': ByteDanceSeleniumCrawler,
    'tencent': TencentSeleniumCrawler,
}


class MultiCompanySeleniumCrawler:
    """多公司Selenium爬虫管理器"""
    
    def __init__(self, companies: List[str] = None, output_dir: str = '.', headless: bool = True):
        self.companies = companies or list(SELENIUM_CRAWLER_REGISTRY.keys())
        self.output_dir = Path(output_dir)
        self.headless = headless
        self.all_jobs: List[Dict] = []
    
    def crawl_all(self) -> List[Dict]:
        """爬取所有公司"""
        logger.info(f"准备爬取 {len(self.companies)} 家公司...")
        logger.info(f"公司列表: {', '.join(self.companies)}")
        
        for company in self.companies:
            if company not in SELENIUM_CRAWLER_REGISTRY:
                logger.warning(f"Selenium爬虫不支持: {company}")
                continue
            
            try:
                crawler = SELENIUM_CRAWLER_REGISTRY[company](headless=self.headless)
                jobs = crawler.crawl()
                self.all_jobs.extend(jobs)
            except Exception as e:
                logger.error(f"爬取 {company} 失败: {e}")
        
        logger.info(f"\n爬取完成! 共获取 {len(self.all_jobs)} 个岗位")
        return self.all_jobs
    
    def save(self, filename: str = None) -> str:
        """保存结果"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"all_jobs_selenium_{timestamp}.json"
        
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.all_jobs, f, ensure_ascii=False, indent=2)
        
        logger.info(f"数据已保存到: {output_path}")
        self._print_statistics()
        return str(output_path)
    
    def _print_statistics(self):
        """打印统计"""
        from collections import Counter
        
        company_counts = Counter(job['company_name'] for job in self.all_jobs)
        
        logger.info("\n📊 统计信息:")
        for company, count in sorted(company_counts.items(), key=lambda x: -x[1]):
            logger.info(f"  {company}: {count} 个岗位")


def main():
    parser = argparse.ArgumentParser(description='招聘信息爬虫 (Selenium版)')
    parser.add_argument('--companies', '-c', nargs='+', default=['all'])
    parser.add_argument('--output', '-o', default='.')
    parser.add_argument('--filename', '-f', default=None)
    parser.add_argument('--no-headless', action='store_true', help='显示浏览器窗口')
    parser.add_argument('--list', '-l', action='store_true')
    
    args = parser.parse_args()
    
    if args.list:
        print("\n支持的公司 (Selenium版):")
        for name in SELENIUM_CRAWLER_REGISTRY:
            print(f"  - {name}")
        return
    
    if not SELENIUM_AVAILABLE:
        print("请先安装Selenium:")
        print("  pip install selenium webdriver-manager")
        return
    
    companies = None if 'all' in args.companies else args.companies
    
    crawler = MultiCompanySeleniumCrawler(
        companies=companies,
        output_dir=args.output,
        headless=not args.no_headless
    )
    crawler.crawl_all()
    crawler.save(filename=args.filename)


if __name__ == '__main__':
    main()
