#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
岗位数据更新脚本
一键爬取最新数据并更新到网站
"""

import subprocess
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).parent

def run_crawler(companies='all'):
    """运行爬虫"""
    print("\n" + "="*60)
    print("📥 步骤1: 爬取最新岗位数据")
    print("="*60)
    
    output_file = ROOT_DIR / "all_companies_jobs.json"
    
    cmd = [
        sys.executable, 
        str(ROOT_DIR / "job_crawler.py"),
        "-c", companies,
        "-f", "all_companies_jobs.json"
    ]
    
    result = subprocess.run(cmd, cwd=str(ROOT_DIR))
    
    if result.returncode == 0 and output_file.exists():
        with open(output_file, 'r', encoding='utf-8') as f:
            jobs = json.load(f)
        print(f"✅ 爬取完成: {len(jobs)} 个岗位")
        return True
    else:
        print("❌ 爬取失败")
        return False


def backup_old_data():
    """备份旧数据"""
    jobs_file = ROOT_DIR / "all_companies_jobs.json"
    if jobs_file.exists():
        backup_name = f"all_companies_jobs_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        backup_path = ROOT_DIR / backup_name
        shutil.copy(jobs_file, backup_path)
        print(f"📦 已备份旧数据到: {backup_name}")


def restart_backend():
    """提示重启后端"""
    print("\n" + "="*60)
    print("🔄 步骤2: 重启后端服务")
    print("="*60)
    print("""
请手动重启后端服务以加载最新数据:

方式1 - 如果后端在后台运行:
  pkill -f "python api_server.py"
  cd "{}"
  python api_server.py &

方式2 - 如果使用终端:
  按 Ctrl+C 停止当前运行的后端
  重新运行: python api_server.py

方式3 - 访问网站刷新:
  打开 http://localhost:8080
  岗位页面会自动加载最新数据
""".format(ROOT_DIR))


def show_stats():
    """显示数据统计"""
    jobs_file = ROOT_DIR / "all_companies_jobs.json"
    if not jobs_file.exists():
        return
    
    with open(jobs_file, 'r', encoding='utf-8') as f:
        jobs = json.load(f)
    
    from collections import Counter
    company_counts = Counter(job['company_name'] for job in jobs)
    
    print("\n" + "="*60)
    print("📊 数据统计")
    print("="*60)
    print(f"\n总岗位数: {len(jobs)}")
    print("\n按公司统计:")
    for company, count in sorted(company_counts.items(), key=lambda x: -x[1]):
        print(f"  {company}: {count} 个")
    print()


def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║           岗位数据更新工具                               ║
╚══════════════════════════════════════════════════════════╝
""")
    
    # 1. 备份
    backup_old_data()
    
    # 2. 爬取
    success = run_crawler()
    
    if success:
        # 3. 显示统计
        show_stats()
        
        # 4. 提示重启
        restart_backend()
        
        print("\n✅ 更新完成！刷新网站即可看到最新数据。")
    else:
        print("\n❌ 更新失败，请检查网络连接。")


if __name__ == '__main__':
    main()
