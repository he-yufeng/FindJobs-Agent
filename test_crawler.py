#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬虫API测试脚本
测试各大厂招聘API的可访问性
"""

import requests
import json
import time

# 禁用SSL警告
import urllib3
urllib3.disable_warnings()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'application/json',
}

def test_api(name: str, url: str, method: str = 'GET', **kwargs):
    """测试单个API"""
    print(f"\n{'='*50}")
    print(f"测试 {name}")
    print(f"URL: {url}")
    print(f"{'='*50}")
    
    try:
        kwargs['headers'] = kwargs.get('headers', HEADERS)
        kwargs['timeout'] = 15
        kwargs['verify'] = False
        
        if method == 'GET':
            resp = requests.get(url, **kwargs)
        else:
            resp = requests.post(url, **kwargs)
        
        print(f"状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                # 尝试获取岗位数量
                if isinstance(data, dict):
                    # 尝试多种可能的数据路径
                    count = (
                        data.get('Data', {}).get('Count') or
                        data.get('data', {}).get('total') or
                        data.get('content', {}).get('data', {}).get('page', {}).get('total') or
                        len(data.get('data', {}).get('list', [])) or
                        len(data.get('Data', {}).get('Posts', [])) or
                        '未知'
                    )
                    print(f"✅ 成功! 岗位数量: {count}")
                    print(f"响应预览: {json.dumps(data, ensure_ascii=False)[:300]}...")
                else:
                    print(f"✅ 成功! 返回数据类型: {type(data)}")
            except:
                print(f"✅ 请求成功，但响应非JSON")
                print(f"响应预览: {resp.text[:200]}...")
        else:
            print(f"❌ 失败: HTTP {resp.status_code}")
            print(f"响应: {resp.text[:200]}...")
            
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    time.sleep(1)


def main():
    print("\n" + "="*60)
    print("🔍 招聘网站API可访问性测试")
    print("="*60)
    
    # 1. 腾讯
    test_api(
        "腾讯招聘 (社招)",
        "https://careers.tencent.com/tencentcareer/api/post/Query",
        params={
            'pageIndex': 1,
            'pageSize': 5,
            'language': 'zh-cn',
            'area': 'cn'
        }
    )
    
    # 2. 字节跳动
    test_api(
        "字节跳动招聘",
        "https://jobs.bytedance.com/api/v1/search/job/posts",
        params={
            'keyword': '',
            'limit': 5,
            'offset': 0,
            'recruit_type': 'campus'
        }
    )
    
    # 3. 阿里巴巴
    test_api(
        "阿里巴巴招聘",
        "https://talent.alibaba.com/off_campus/position/list",
        method='POST',
        json={
            'pageSize': 5,
            'pageIndex': 1,
            'language': 'zh',
            'channel': 'group_official_site'
        },
        headers={
            **HEADERS,
            'Content-Type': 'application/json',
            'Referer': 'https://talent.alibaba.com/'
        }
    )
    
    # 4. 百度
    test_api(
        "百度招聘",
        "https://talent.baidu.com/httservice/getPostListNew",
        method='POST',
        json={
            'recruitType': 'SOCIAL',
            'pageSize': 5,
            'curPage': 1
        },
        headers={
            **HEADERS,
            'Content-Type': 'application/json'
        }
    )
    
    # 5. 美团
    test_api(
        "美团招聘",
        "https://zhaopin.meituan.com/api/recruitment/v2/jobs",
        params={
            'limit': 5,
            'offset': 0,
            'jobType': 1
        }
    )
    
    # 6. 京东
    test_api(
        "京东招聘",
        "https://zhaopin.jd.com/web/job/job_list",
        params={
            'page': 1,
            'limit': 5
        }
    )
    
    # 7. 网易
    test_api(
        "网易招聘",
        "https://hr.163.com/api/hr163/position/queryPage",
        method='POST',
        json={
            'currentPage': 1,
            'pageSize': 5
        },
        headers={
            **HEADERS,
            'Content-Type': 'application/json'
        }
    )
    
    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)
    print("\n提示:")
    print("- 如果大部分API显示❌，可能是网络环境问题")
    print("- 建议使用VPN或配置代理后重试")
    print("- 也可以使用Selenium版本爬虫绕过限制")


if __name__ == '__main__':
    main()
