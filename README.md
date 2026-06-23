<div align="center">

<img src="docs/banner.png" alt="FindJobs-Agent" width="100%">

[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![React](https://img.shields.io/badge/Frontend-React-61DAFB.svg?logo=react&logoColor=white)](https://react.dev/)
[![Flask](https://img.shields.io/badge/Backend-Flask-000000.svg?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/he-yufeng/FindJobs-Agent?style=social)](https://github.com/he-yufeng/FindJobs-Agent)

**[English](README.md) · [中文](README_CN.md)** &nbsp;·&nbsp; [Quick Start](#quick-start) · [How It Works](#how-it-works) · [Features](#features)

</div>

---

## What is FindJobs-Agent?

A full-stack job search assistant that crawls postings from major tech companies, analyzes them with LLMs, parses your resume, and runs AI mock interviews — so you can focus on preparing, not sifting through job boards.

## How It Works

![FindJobs-Agent architecture](docs/architecture.png)

## Features

### Job Crawler
- Crawl job postings from Tencent, NetEase, ByteDance, Amazon, and more
- Dual mode: API crawling + Selenium browser automation
- Automatic data cleaning and format normalization

### LLM Job Analysis
- Extract education and major requirements automatically
- Skill tag recognition with importance scoring (1-5)
- Job taxonomy classification (primary/secondary categories)

### Resume Parsing & Matching
- Parse PDF/Word resumes intelligently
- Extract and score skill tags
- Calculate job-resume match percentage with case-insensitive skill matching
- Accept skill tags from multiple pipeline formats (`Python , 5 , AI`, `Python %> 5 , AI`, `Python: 5`)

### AI Mock Interview
- Generate targeted interview questions from job descriptions
- Multi-turn conversational interview simulation
- Real-time feedback and suggestions

## Project Structure

```
FindJobs-Agent/
├── FrontEnd/                # React frontend
│   ├── src/
│   │   ├── components/      # Page components
│   │   │   ├── JobsPage.tsx       # Job browsing
│   │   │   ├── ResumePage.tsx     # Resume analysis
│   │   │   └── InterviewPage.tsx  # AI interview
│   │   └── App.tsx
│   └── package.json
├── job_crawler_v2.py        # Multi-company crawler (primary)
├── job_crawler_selenium.py  # Selenium crawler
├── job_agent.py             # LLM job analysis agent
├── pipeline.py              # Data processing pipeline
├── api_server.py            # Flask API server
├── AI_interviewer.py        # AI interview module
├── resume_parser.py         # Resume parser
├── tag_rate.py              # Skill scoring
├── llm_client.py            # LLM client
├── tech_taxonomy.json       # Job taxonomy
├── all_labels.csv           # Skill tag library
└── requirements.txt
```

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- Chrome (required for Selenium crawler)

### 1. Clone the repo
```bash
git clone https://github.com/he-yufeng/FindJobs-Agent.git
cd FindJobs-Agent
```

### 2. Install backend dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up your API key
Create an `API_key.md` file with your OpenAI API key:
```
sk-your-api-key-here
```

### 4. Start the backend
```bash
python api_server.py
```

### 5. Start the frontend
```bash
cd FrontEnd
npm install
npm run dev
```

### 6. Open the app
Visit http://localhost:8080 in your browser.

## Data Pipeline

The processing flow goes through four stages:

1. **Crawl** (`job_crawler_v2.py`) — Fetch job postings from company career sites
2. **Analyze** (`job_agent.py`) — LLM extracts requirements, skills, and classifications
3. **Score** (`tag_rate.py`) — Match and score skill tags against the taxonomy
4. **Serve** (`api_server.py`) — Expose results via REST API for the frontend

### Run the full pipeline
```bash
# Crawl + analyze + generate website data
python pipeline.py

# Crawl only
python job_crawler_v2.py -c tencent netease amazon -m 300

# Analyze only (for testing)
python pipeline.py --analyze-only --max-jobs 50
```

## Key Modules

### job_crawler_v2.py
Multi-company job crawler supporting:
- Tencent, NetEase, ByteDance, Amazon (stable, API-based)
- Alibaba, Meituan, JD, etc. (Selenium mode)

```bash
# Crawl specific companies
python job_crawler_v2.py -c tencent netease -m 500

# List supported companies
python job_crawler_v2.py --list
```

### job_agent.py
LLM-driven job analysis agent:
- Education requirement extraction (Bachelor's/Master's/PhD)
- Major requirement identification
- Skill tag matching and scoring
- Job classification

### AI_interviewer.py
AI mock interview system:
- Generates interview questions from job descriptions
- Multi-turn conversational interaction
- Answer evaluation and feedback

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jobs` | GET | List job postings |
| `/api/jobs/<id>` | GET | Get job details |
| `/api/resume/upload` | POST | Upload resume |
| `/api/resume/analyze` | POST | Analyze resume |
| `/api/interview/start` | POST | Start mock interview |
| `/api/interview/answer` | POST | Submit interview answer |

## Roadmap

Crawl, analyze, resume match, and mock interview work end to end. The next steps widen the funnel and follow the hunt past the match:

- **More job sources** — extend the crawler beyond the current company set to job boards and aggregators, so matching isn't limited to a fixed list.
- **Incremental crawls** — track which postings were already seen and fetch only new ones, instead of re-crawling and re-analyzing the full set each run.
- **Application tracking** — a simple board for where each application stands (applied / replied / interview), so the tool follows the job hunt past the match step.
- **Voice mock interviews** — speech in and out for the AI interviewer, closer to a real screen than a text chat.

## Contributing

Issues and pull requests are welcome!

## License

MIT License
