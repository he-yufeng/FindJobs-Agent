<div align="center">

<img src="docs/banner.png" alt="FindJobs-Agent" width="100%">

[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![React](https://img.shields.io/badge/Frontend-React-61DAFB.svg?logo=react&logoColor=white)](https://react.dev/)
[![Flask](https://img.shields.io/badge/Backend-Flask-000000.svg?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/he-yufeng/FindJobs-Agent?style=social)](https://github.com/he-yufeng/FindJobs-Agent)

**[English](README.md) · [中文](README_CN.md)** &nbsp;·&nbsp; [快速开始](#快速开始) · [工作流程](#工作流程) · [核心功能](#核心功能)

</div>

---

## 简介

一个集成了岗位数据爬取、LLM 智能分析、简历解析和 AI 模拟面试的全栈求职辅助系统。

## 工作流程

![FindJobs-Agent 架构](docs/architecture.png)

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
- 岗位-简历匹配度计算，技能名匹配不区分大小写
- 兼容多种流水线技能标签格式（`Python , 5 , AI`、`Python %> 5 , AI`、`Python: 5`）

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

## 后续规划

爬取、分析、简历匹配、模拟面试已经能跑通整条链路，接下来想把入口拓宽、把求职跟到匹配之后：

- **更多岗位来源**：把爬虫从当前的公司列表扩展到招聘平台和聚合站，让匹配不再局限于固定名单。
- **增量爬取**：记录已经见过的岗位，只抓新发布的，而不是每次重爬、重分析全量。
- **投递进度跟踪**：一个简单看板记录每份投递的状态（已投 / 已回 / 面试），让工具一直跟到匹配之后。
- **语音模拟面试**：给 AI 面试官加上语音输入输出，比纯文字聊天更接近真实面试。

## 相关项目

FindJobs-Agent 是我做的应用级 agent 之一，下面几个也许对你有用：

- **[CoreCoder](https://github.com/he-yufeng/CoreCoder)** — 想搞懂一个 coding agent 到底怎么运作？把整套约 1000 行引擎从头读到尾，而不是当黑箱。
- **[RepoWiki](https://github.com/he-yufeng/RepoWiki)** — 被丢进一个陌生代码库？它给你一份带「从哪读起」路径的 wiki，一个可自托管的 DeepWiki 替代。
- **[ContractGuard](https://github.com/he-yufeng/ContractGuard)** — 签字前先把有风险的条款挑出来：它读合同、标出危险点。
- **[GitSense](https://github.com/he-yufeng/GitSense)** — 想给开源做贡献？它帮你找到值得做的 issue，还能估你的 PR 多大概率被合。
- **[CodeABC](https://github.com/he-yufeng/CodeABC)** — 不会写代码也能看懂一个项目，专给小白做的。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License
