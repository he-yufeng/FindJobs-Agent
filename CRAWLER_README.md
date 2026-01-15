# 招聘信息爬虫使用指南

本项目提供两个版本的招聘爬虫，用于爬取主流互联网大厂的招聘信息。

## 📦 支持的公司

| 公司 | API版本 | Selenium版本 |
|------|---------|--------------|
| 字节跳动 | ✅ | ✅ |
| 腾讯 | ✅ | ✅ |
| 阿里巴巴 | ✅ | 🚧 |
| 百度 | ✅ | 🚧 |
| 美团 | ✅ | 🚧 |
| 京东 | ✅ | 🚧 |
| 快手 | ✅ | 🚧 |
| 网易 | ✅ | 🚧 |
| 小米 | ✅ | 🚧 |

## 🔧 安装依赖

### 方式1: API版本（轻量级）
```bash
pip install requests pandas
```

### 方式2: Selenium版本（需要浏览器）
```bash
pip install selenium webdriver-manager
```

#### 安装Chrome浏览器和驱动

**macOS:**
```bash
# 安装Chrome (如果没有)
brew install --cask google-chrome

# chromedriver会自动下载，或手动安装:
brew install chromedriver
```

**Ubuntu/Debian:**
```bash
# 安装Chrome
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
sudo apt update
sudo apt install google-chrome-stable

# chromedriver
sudo apt install chromium-chromedriver
```

**Windows:**
1. 下载并安装 Chrome: https://www.google.com/chrome/
2. 下载对应版本的 chromedriver: https://chromedriver.chromium.org/downloads
3. 将 chromedriver.exe 放入 PATH 路径

## 🚀 使用方法

### API版本 (job_crawler.py)

```bash
# 查看支持的公司
python job_crawler.py --list

# 爬取所有公司
python job_crawler.py

# 爬取特定公司
python job_crawler.py -c bytedance tencent alibaba

# 指定输出文件
python job_crawler.py -c bytedance -f bytedance_jobs.json

# 并行爬取（更快但可能触发反爬）
python job_crawler.py -c bytedance tencent -p
```

### Selenium版本 (job_crawler_selenium.py)

```bash
# 查看支持的公司
python job_crawler_selenium.py --list

# 爬取（默认无头模式）
python job_crawler_selenium.py -c bytedance

# 显示浏览器窗口（调试用）
python job_crawler_selenium.py -c bytedance --no-headless
```

## 📊 输出格式

爬取的数据保存为JSON格式，与项目原有的 `bytedance_jobs.json` 格式完全兼容：

```json
[
  {
    "company_name": "字节跳动",
    "job_title": "AI广告产品实习生",
    "job_id": "A56534",
    "category": "实习",
    "location": "北京",
    "job_type": "产品",
    "special_program": "抖音生活服务",
    "job_description": "职位描述...",
    "job_requirements": "职位要求...",
    "apply_url": "https://...",
    "source_url": "https://..."
  }
]
```

## ⚠️ 注意事项

### 反爬虫措施

1. **请求频率**: 爬虫已内置随机延迟（1-3秒），请勿修改得太快
2. **IP限制**: 如果被封IP，建议：
   - 使用代理
   - 降低爬取频率
   - 使用Selenium版本
3. **SSL错误**: 如遇到SSL错误，可能需要：
   - 使用VPN
   - 配置代理

### 代理配置

编辑 `job_crawler.py` 中的 `PROXY` 变量：

```python
PROXY = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890'
}
```

### 合规提醒

- 请遵守各网站的 robots.txt 和服务条款
- 仅用于学习和研究目的
- 不要进行大规模商业爬取
- 尊重数据隐私

## 🔄 合并数据

爬取后可以合并多个JSON文件：

```python
import json
from pathlib import Path

all_jobs = []
for f in Path('.').glob('*_jobs.json'):
    with open(f, 'r', encoding='utf-8') as fp:
        all_jobs.extend(json.load(fp))

# 去重
seen = set()
unique_jobs = []
for job in all_jobs:
    key = (job['company_name'], job['job_id'])
    if key not in seen:
        seen.add(key)
        unique_jobs.append(job)

# 保存
with open('all_companies_jobs.json', 'w', encoding='utf-8') as f:
    json.dump(unique_jobs, f, ensure_ascii=False, indent=2)

print(f"合并完成: {len(unique_jobs)} 个岗位")
```

## 🐛 常见问题

### Q: SSL错误
```
SSLError: [SSL: KRB5_S_TKT_NYV] unexpected eof while reading
```
**解决**: 网络环境问题，尝试使用VPN或代理。

### Q: ChromeDriver版本不匹配
```
Message: session not created: This version of ChromeDriver only supports Chrome version XX
```
**解决**: 更新chromedriver到与Chrome匹配的版本，或使用 `webdriver-manager` 自动管理。

### Q: 请求被拒绝/403
**解决**: 
1. 降低请求频率
2. 使用Selenium版本
3. 更换IP/使用代理

## 📝 扩展开发

如需添加新公司的爬虫，参考 `ByteDanceCrawler` 类实现：

```python
class NewCompanyCrawler(JobCrawlerBase):
    @property
    def company_name(self) -> str:
        return "新公司"
    
    def crawl(self) -> List[Dict]:
        # 实现爬取逻辑
        pass

# 注册到爬虫表
CRAWLER_REGISTRY['newcompany'] = NewCompanyCrawler
```

---

**最后更新**: 2026-01-15
