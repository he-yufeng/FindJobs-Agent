#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
岗位数据处理流水线

完整流程：
1. 爬取原始岗位数据 (job_crawler_v2.py)
2. 智能分析提取 (job_agent.py) - 使用LLM提取学历、技能、评分等
3. 生成网站可用数据

这个脚本整合了爬虫和智能分析两个步骤！
"""

import argparse
import json
import logging
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

ROOT_DIR = Path(__file__).parent

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_banner(text: str):
    """打印横幅"""
    width = 60
    print(f"\n{'='*width}")
    print(f"  {text}")
    print(f"{'='*width}\n")


def backup_existing_data():
    """备份现有数据"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 备份原始JSON
    raw_file = ROOT_DIR / 'crawled_jobs_raw.json'
    if raw_file.exists():
        backup = ROOT_DIR / f'backup/crawled_jobs_raw_{timestamp}.json'
        backup.parent.mkdir(exist_ok=True)
        shutil.copy(raw_file, backup)
        logger.info(f"📦 备份原始数据: {backup.name}")
    
    # 备份分析后的CSV
    enriched_file = ROOT_DIR / 'jobs_enriched.csv'
    if enriched_file.exists():
        backup = ROOT_DIR / f'backup/jobs_enriched_{timestamp}.csv'
        backup.parent.mkdir(exist_ok=True)
        shutil.copy(enriched_file, backup)
        logger.info(f"📦 备份分析数据: {backup.name}")


def step1_crawl_jobs(companies: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    步骤1: 爬取原始岗位数据
    """
    print_banner("步骤 1/3: 爬取原始岗位数据")
    
    cmd = [
        sys.executable,
        str(ROOT_DIR / 'job_crawler_v2.py'),
        '-f', 'crawled_jobs_raw.json'
    ]
    
    if companies:
        cmd.extend(['-c'] + companies)
    
    logger.info(f"运行爬虫: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT_DIR))
    
    # 读取结果
    raw_file = ROOT_DIR / 'crawled_jobs_raw.json'
    if raw_file.exists():
        with open(raw_file, 'r', encoding='utf-8') as f:
            jobs = json.load(f)
        logger.info(f"✅ 爬取完成: {len(jobs)} 个原始岗位")
        return {'success': True, 'count': len(jobs), 'file': str(raw_file)}
    else:
        logger.error("❌ 爬取失败: 未生成输出文件")
        return {'success': False, 'count': 0}


def step2_analyze_with_llm(max_jobs: Optional[int] = None) -> Dict[str, Any]:
    """
    步骤2: 使用LLM智能分析（调用job_agent.py）
    
    这一步会：
    - 分析每个岗位的学历要求
    - 提取专业要求
    - 从技能库中匹配技能并评分(1-5分)
    - 分类岗位族(job_level1, job_level2)
    """
    print_banner("步骤 2/3: LLM智能分析提取")
    
    raw_file = ROOT_DIR / 'crawled_jobs_raw.json'
    if not raw_file.exists():
        logger.error("❌ 未找到原始数据文件")
        return {'success': False}
    
    # 读取原始数据
    with open(raw_file, 'r', encoding='utf-8') as f:
        jobs = json.load(f)
    
    total_jobs = len(jobs)
    logger.info(f"📊 待分析岗位总数: {total_jobs}")
    
    # 如果指定了最大数量，截取部分数据
    if max_jobs and max_jobs < total_jobs:
        logger.info(f"⚠️  将只分析前 {max_jobs} 个岗位（完整分析请移除 --max-jobs 参数）")
        jobs = jobs[:max_jobs]
        # 保存截取后的数据
        temp_file = ROOT_DIR / 'temp_jobs_for_analysis.json'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
        input_file = temp_file
    else:
        input_file = raw_file
    
    output_file = ROOT_DIR / 'jobs_enriched.csv'
    
    # 调用 job_agent.py 进行智能分析
    cmd = [
        sys.executable,
        str(ROOT_DIR / 'job_agent.py'),
        '--jobs-file', str(input_file),
        '--output-file', str(output_file),
        '--min-skills', '3',
        '--max-skills', '10',
        '--max-workers', '5',  # 控制并发，避免API限流
    ]
    
    logger.info(f"运行智能分析: job_agent.py")
    logger.info(f"输入文件: {input_file}")
    logger.info(f"输出文件: {output_file}")
    logger.info("")
    logger.info("🤖 正在调用LLM分析（这可能需要较长时间）...")
    logger.info("   - 提取学历要求")
    logger.info("   - 提取专业要求")
    logger.info("   - 匹配技能并评分(1-5分)")
    logger.info("   - 分类岗位族")
    logger.info("")
    
    try:
        result = subprocess.run(cmd, cwd=str(ROOT_DIR), timeout=7200)  # 2小时超时
        
        if output_file.exists():
            # 读取分析后的数据统计
            import pandas as pd
            df = pd.read_csv(output_file)
            
            # 统计有技能标签的岗位
            has_skills = df['skill_tags'].notna().sum()
            
            logger.info(f"✅ 智能分析完成")
            logger.info(f"   - 总岗位数: {len(df)}")
            logger.info(f"   - 有技能标签: {has_skills}")
            
            return {
                'success': True,
                'count': len(df),
                'file': str(output_file),
            }
        else:
            logger.error("❌ 分析失败: 未生成输出文件")
            return {'success': False}
            
    except subprocess.TimeoutExpired:
        logger.error("❌ 分析超时（超过2小时）")
        return {'success': False}
    except Exception as e:
        logger.error(f"❌ 分析失败: {e}")
        return {'success': False}


def step3_prepare_for_website() -> Dict[str, Any]:
    """
    步骤3: 准备网站数据
    
    将分析后的CSV转换为网站使用的JSON格式
    """
    print_banner("步骤 3/3: 准备网站数据")
    
    enriched_csv = ROOT_DIR / 'jobs_enriched.csv'
    output_json = ROOT_DIR / 'all_companies_jobs.json'
    
    if not enriched_csv.exists():
        # 如果没有分析后的数据，使用原始数据
        raw_json = ROOT_DIR / 'crawled_jobs_raw.json'
        if raw_json.exists():
            logger.warning("⚠️  未找到分析后的数据，将使用原始数据")
            shutil.copy(raw_json, output_json)
            with open(output_json, 'r', encoding='utf-8') as f:
                jobs = json.load(f)
            logger.info(f"📁 网站数据已更新: {output_json.name} ({len(jobs)} 个岗位)")
            return {'success': True, 'count': len(jobs), 'enriched': False}
        else:
            logger.error("❌ 未找到任何数据文件")
            return {'success': False}
    
    # 读取分析后的CSV
    import pandas as pd
    df = pd.read_csv(enriched_csv)
    
    # 转换为JSON格式（保持与原有格式兼容）
    jobs = []
    for _, row in df.iterrows():
        job = {
            'company_name': str(row.get('company_name', '')),
            'job_title': str(row.get('job_title', '')),
            'job_id': str(row.get('job_id', '')),
            'category': str(row.get('category', '')),
            'location': str(row.get('location', '')),
            'job_type': str(row.get('job_type', '')),
            'special_program': str(row.get('special_program', '')),
            'job_description': str(row.get('job_description', '')),
            'job_requirements': str(row.get('job_requirements', '')),
            'apply_url': str(row.get('apply_url', '')),
            'source_url': str(row.get('source_url', '')),
            # 智能分析提取的字段
            'min_degree': str(row.get('min_degree', '')),
            'degree_priority': str(row.get('degree_priority', '')),
            'major_requirement': str(row.get('major_requirement_text', '')),
            'skill_tags': str(row.get('skill_tags', '')),
            'job_level1': str(row.get('job_level1', '')),
            'job_level2': str(row.get('job_level2', '')),
        }
        jobs.append(job)
    
    # 保存JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ 网站数据已更新: {output_json.name}")
    logger.info(f"   - 总岗位数: {len(jobs)}")
    
    # 统计
    companies = {}
    for job in jobs:
        company = job['company_name']
        companies[company] = companies.get(company, 0) + 1
    
    logger.info(f"\n📊 按公司统计:")
    for company, count in sorted(companies.items(), key=lambda x: -x[1]):
        has_skills = sum(1 for j in jobs if j['company_name'] == company and j.get('skill_tags'))
        logger.info(f"   {company:15}: {count:5} 个 (含技能标签: {has_skills})")
    
    return {'success': True, 'count': len(jobs), 'enriched': True}


def show_next_steps():
    """显示下一步操作"""
    print_banner("下一步操作")
    
    print("""
数据更新完成！请按以下步骤操作：

1. 重启后端服务:
   pkill -f "python api_server.py"
   PORT=5001 python api_server.py &

2. 打开网站查看:
   http://localhost:8080

3. 网站将显示:
   - 岗位列表（含技能标签和评分）
   - 学历要求、专业要求
   - 岗位分类(job_level1/job_level2)
""")


def main():
    parser = argparse.ArgumentParser(
        description='岗位数据处理流水线',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python pipeline.py                    # 完整流程（爬取+分析+更新网站）
  python pipeline.py --crawl-only       # 只爬取，不分析
  python pipeline.py --analyze-only     # 只分析已爬取的数据
  python pipeline.py --max-jobs 100     # 只分析前100个岗位（测试用）
  python pipeline.py -c tencent amazon  # 只爬取指定公司
        """
    )
    
    parser.add_argument('-c', '--companies', nargs='*', default=None,
                        help='指定要爬取的公司')
    parser.add_argument('--crawl-only', action='store_true',
                        help='只执行爬取步骤')
    parser.add_argument('--analyze-only', action='store_true',
                        help='只执行分析步骤（使用已有的原始数据）')
    parser.add_argument('--max-jobs', type=int, default=None,
                        help='限制分析的岗位数量（用于测试）')
    parser.add_argument('--no-backup', action='store_true',
                        help='不备份现有数据')
    
    args = parser.parse_args()
    
    print_banner("岗位数据处理流水线")
    
    print("""
本流水线包含三个步骤:
  1. 爬取原始岗位数据
  2. LLM智能分析提取（学历、技能评分、岗位分类）
  3. 生成网站可用数据
""")
    
    # 备份
    if not args.no_backup:
        backup_existing_data()
    
    # 执行步骤
    if args.analyze_only:
        # 只分析
        result2 = step2_analyze_with_llm(args.max_jobs)
        if result2['success']:
            step3_prepare_for_website()
    elif args.crawl_only:
        # 只爬取
        step1_crawl_jobs(args.companies)
    else:
        # 完整流程
        result1 = step1_crawl_jobs(args.companies)
        if result1['success']:
            result2 = step2_analyze_with_llm(args.max_jobs)
            if result2['success']:
                step3_prepare_for_website()
            else:
                logger.warning("智能分析失败，使用原始数据")
                step3_prepare_for_website()
        else:
            logger.error("爬取失败，流水线中止")
            return
    
    show_next_steps()


if __name__ == '__main__':
    main()
