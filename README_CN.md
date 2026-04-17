<div align="center">

# FindJobs-Agent

**基于大语言模型的智能求职平台 — 从岗位爬取到模拟面试，一站搞定。**

[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/he-yufeng/FindJobs-Agent?style=social)](https://github.com/he-yufeng/FindJobs-Agent)

**[English](README.md) | [中文](README_CN.md)**

</div>

---

## 简介

一个集成了岗位数据爬取、LLM 智能分析、简历解析和 AI 模拟面试的全栈求职辅助系统。

## 核心功能

### 智能岗位爬虫
- 支持多家大厂招聘数据爬取（腾讯、网易、字节跳动、Amazon 等）
- API 爬取 + Selenium 浏览器自动化双模式
- 自动数据清洗和格式标准化

### LLM 智能分析
- 自动提取岗位学历要求、专业要求
- 技能标签识别与重要性评分（1-5 分）
- 岗位族谱分类（一级/二级分类）

### 简历解析与匹配
- PDF/Word 简历智能解析
- 技能标签提取与评分
- 岗位-简历匹配度计算

### AI 模拟面试
- 基于岗位 JD 生成针对性面试问题
- 多轮对话式面试模拟
- 实时反馈与建议

## 项目结构

```
FindJobs-Agent/
├── FrontEnd/                # React 前端
│   ├── src/
│   │   ├── components/      # 页面组件
│   │   │   ├── JobsPage.tsx       # 岗位浏览
│   │   │   ├── ResumePage.tsx     # 简历分析
│   │   │   └── InterviewPage.tsx  # AI 面试
│   │   └── App.tsx
│   └── package.json
├── job_crawler_v2.py        # 多公司爬虫（主力）
├── job_crawler_selenium.py  # Selenium 爬虫
├── job_agent.py             # LLM 岗位分析 Agent
├── pipeline.py              # 数据处理流水线
├── api_server.py            # Flask API 服务
├── AI_interviewer.py        # AI 面试模块
├── resume_parser.py         # 简历解析
├── tag_rate.py              # 技能评分
├── llm_client.py            # LLM 客户端
├── tech_taxonomy.json       # 岗位分类体系
├── all_labels.csv           # 技能标签库
└── requirements.txt
```

## 快速开始

### 环境要求
- Python 3.9+
- Node.js 18+
- Chrome 浏览器（Selenium 爬虫需要）

### 1. 克隆项目
```bash
git clone https://github.com/he-yufeng/FindJobs-Agent.git
cd FindJobs-Agent
```

### 2. 安装后端依赖
```bash
pip install -r requirements.txt
```

### 3. 配置 API Key
创建 `API_key.md` 文件，填入你的 OpenAI API Key：
```
sk-your-api-key-here
```

### 4. 启动后端服务
```bash
python api_server.py
```

### 5. 启动前端
```bash
cd FrontEnd
npm install
npm run dev
```

### 6. 访问应用
打开浏览器访问 http://localhost:8080

## 数据处理流程

处理流水线分为四个阶段：

1. **爬取** (`job_crawler_v2.py`) — 从各公司招聘网站抓取岗位信息
2. **分析** (`job_agent.py`) — LLM 提取岗位要求、技能标签和分类
3. **评分** (`tag_rate.py`) — 技能标签匹配与重要性打分
4. **展示** (`api_server.py`) — REST API 提供数据给前端展示

### 一键运行数据流水线
```bash
# 爬取 + 分析 + 生成网站数据
python pipeline.py

# 仅爬取
python job_crawler_v2.py -c tencent netease amazon -m 300

# 仅分析（测试）
python pipeline.py --analyze-only --max-jobs 50
```

## 主要模块说明

### job_crawler_v2.py
多公司岗位爬虫，支持：
- 腾讯、网易、字节跳动、Amazon（稳定，API 模式）
- 阿里、美团、京东等（Selenium 模式）

```bash
# 爬取指定公司
python job_crawler_v2.py -c tencent netease -m 500

# 列出支持的公司
python job_crawler_v2.py --list
```

### job_agent.py
LLM 驱动的岗位分析 Agent：
- 学历要求提取（本科/硕士/博士）
- 专业要求识别
- 技能标签匹配与评分
- 岗位分类

### AI_interviewer.py
AI 模拟面试系统：
- 根据 JD 生成面试问题
- 多轮对话交互
- 答案评估与反馈

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/jobs` | GET | 获取岗位列表 |
| `/api/jobs/<id>` | GET | 获取岗位详情 |
| `/api/resume/upload` | POST | 上传简历 |
| `/api/resume/analyze` | POST | 分析简历 |
| `/api/interview/start` | POST | 开始面试 |
| `/api/interview/answer` | POST | 提交答案 |

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License
