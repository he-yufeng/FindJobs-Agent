<div align="center">

<img src="docs/banner.png" alt="FindJobs-Agent" width="100%">

[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/he-yufeng/FindJobs-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/he-yufeng/FindJobs-Agent/actions/workflows/ci.yml)

**[English](README.md) · [中文](README_CN.md)** &nbsp;·&nbsp; [Demo](#try-it-in-2-minutes-demo-mode) · [Quick Start](#quick-start) · [How It Works](#how-it-works) · [Features](#features)

</div>

---

## What is FindJobs-Agent?

A full-stack job search assistant that crawls postings from major tech companies, analyzes them with LLMs, parses your resume, and runs AI mock interviews — so you can focus on preparing, not sifting through job boards.

<p align="center">
  <img src="assets/full-journey-demo.gif" alt="Full journey: crawl → LLM analysis → skill gaps → mock interview" width="100%">
</p>

<p align="center"><em>The whole loop in one terminal run, offline: 54 sample postings crawled and structured, resume×job skill gaps, and a mock interview with a feedback report. Replay it with <code>python examples/full_journey_demo.py</code>.</em></p>

## Try It in 2 Minutes (Demo Mode)

No API key? No problem. Demo mode runs the whole app offline:

```bash
pip install -r requirements.txt
FINDJOBS_DEMO=1 python api_server.py        # backend on :5000, seeds sample jobs on first run
cd FrontEnd && npm install && npm run dev   # frontend on :8080
```

With `FINDJOBS_DEMO=1`, the server fills an empty `jobs.db` from `data/sample_jobs.json` (54 hand-written postings from the companies the crawlers target) and routes every LLM call through `demo_llm.py`, a deterministic stub that answers from the prompt content and never touches the network, even if a key is configured. Upload the bundled `data/sample_resume.pdf` on the resume page to walk the full loop: parsing, match scores, a 3-stage mock interview, and the tracking board. While the backend runs in demo mode, a small "Demo" badge shows in the navbar.

Both fixtures can be regenerated with `python scripts/seed_demo_data.py` and `python scripts/make_sample_resume.py`.

## How It Works

Four pieces wired into one flow: a crawler pulls postings from company career sites, an LLM reads each one for requirements and skills, your resume gets parsed and scored against them, and any posting can drive an AI mock interview straight off its job description. The React frontend ties it together, so you go from "what's out there" to "let me practice for this one" without leaving the app.

![FindJobs-Agent architecture](docs/architecture.png)

## Features

- **Job crawler** — pulls postings from Tencent, NetEase, ByteDance, Amazon and more, via API or Selenium, with automatic cleaning and normalization.
- **LLM analysis** — extracts education/major requirements, scores skill tags (1–5), and classifies each posting into a job taxonomy.
- **Resume parsing & matching** — parses PDF/Word resumes, scores skills, and computes a case-insensitive job-resume match percentage.
- **AI mock interview** — generates questions from any job description and runs a multi-turn interview with real-time feedback.
- **Demo mode**: set `FINDJOBS_DEMO=1` to run the full app offline with seeded sample jobs, a bundled sample resume, and a deterministic stub LLM instead of a paid key.
- **SQLite persistence** — analyzed postings are stored in a local `jobs.db`; existing CSV data is migrated automatically on first run, with CSV/JSON as fallback. Uploaded resumes and mock-interview transcripts live in the same database, so restarting the API server no longer wipes them.

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
├── findjobs/                # The package: crawler, matcher, resume, interview, pipeline
│   ├── pipeline.py          # Main pipeline; also the `findjobs` CLI entry
│   ├── job_agent.py         # LLM job analysis agent
│   ├── api_server.py        # Flask API server
│   ├── storage.py           # SQLite store: jobs, applications, resumes, interviews (jobs.db)
│   ├── interview_agent.py   # AI interview module
│   ├── resume_parser.py     # Resume parser
│   └── ...                  # crawlers, scoring, LLM client, demo stub
├── data/                    # Label library + taxonomy + demo fixtures
├── config/                  # llm_config.json and deployment configs
├── docs/                    # API reference and project notes
├── scripts/                 # Helpers: demo seeding, sample resume generator, crawler smoke test
├── tests/                   # pytest suite
├── pyproject.toml
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

`pipeline.py` chains crawl → analyze → score → serve. Run the whole thing, or a single stage:

```bash
python pipeline.py                                          # crawl + analyze + build site data
python job_crawler_v2.py -c tencent netease amazon -m 300   # crawl only (--list shows companies)
python pipeline.py --analyze-only --max-jobs 50             # analyze only (for testing)
```

An optional aggregator source is available via [freehire.me](https://freehire.me), an open IT job board whose public API needs no key. Each result already carries the full markdown JD and the employer's own ATS apply link, so there is no detail page to re-fetch. It stays off by default; flip it on with `--freehire`, or run it standalone:

```bash
python pipeline.py --freehire --freehire-query "backend"      # company crawlers + freehire
python freehire_source.py -q "ml engineer" --skills python,pytorch --countries us,de -m 100
python freehire_source.py --list-facets skills                # live filter vocabulary (skill slugs, country codes)
```

**Pluggable job sources.** Crawlers, third-party APIs, and local JSON files all enter through one `JobSource` interface (`findjobs/job_source.py`): implement `name` + `fetch()` returning canonical job dicts, then `register_source(...)` — no pipeline edits. The pipeline walks the registry (`company crawlers` by default, `freehire` when enabled), dedupes across sources, and `pipeline.step1_crawl_jobs(sources=[...])` accepts a full replacement list for custom feeds.

Filter vocabularies are read from `/api/v1/jobs/facets` at runtime instead of being hardcoded.

### Job data sources

The crawler knows 32 companies (`--list`), all fetched through the public job APIs that each careers site serves to job seekers. No login, no key, no page scraping behind a wall.

As of the last refresh (2026-09), four sources are live and verified:

| Source | Endpoint | Notes |
|--------|----------|-------|
| Tencent (腾讯) | `careers.tencent.com` query API | up to 400 per pull |
| ByteDance (字节跳动) | `jobs.bytedance.com` portal API | moved to the current POST payload; the old GET form is gone |
| NetEase (网易) | public search API | social + campus |
| Amazon | `amazon.jobs` search API | global, CN filter supported |

`data/latest_jobs.json` holds the latest snapshot: 1,187 postings across these four, committed so the pipeline has real data to chew on without a fresh crawl. `data/latest_enriched.jsonl` is the same set after LLM analysis (degree, major requirement, scored skill tags, job family), so the site and the matcher work out of the box with zero API spend.

The other adapters (Baidu, Kuaishou, Xiaomi, Bilibili, DiDi, Pinduoduo, Huawei, Ctrip, DJI, NIO, XPeng, Li Auto, OPPO, VIVO, SenseTime, MiHoYo, SHEIN, Shopee, KE, Yuanfudao, Zuoyebang, Zhilian, Lagou, Microsoft, Google) were written against 2023-era endpoints that have since changed shape or started blocking plain requests; they currently return empty and need an adapter refresh. Alibaba, Meituan and JD go through `job_crawler_selenium.py` and want a local browser driver. If you rely on one of these, open an issue and it moves up the queue.

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
- **Application tracking** — a board page in the frontend tracks each job through bookmarked / applied / replied / interview / offer / rejected, backed by `/api/applications` in SQLite. Status changes and notes save inline.
- **Voice mock interviews** — speech in and out for the AI interviewer, closer to a real screen than a text chat.

## Related Projects

FindJobs-Agent is one of the applied agents I've built. A few others you might find useful:

- **[CoreCoder](https://github.com/he-yufeng/CoreCoder)** — want to understand how a coding agent really works? Read the whole ~1k-line engine end to end, not a black box.
- **[RepoWiki](https://github.com/he-yufeng/RepoWiki)** — dropped into an unfamiliar codebase? It gives you a guided wiki and a where-to-start reading path, a self-hostable DeepWiki alternative.
- **[ContractGuard](https://github.com/he-yufeng/ContractGuard)** — catch the risky clauses before you sign: it reads contracts and flags the dangerous bits.
- **[GitSense](https://github.com/he-yufeng/GitSense)** — want to contribute to open source? It finds issues worth your time and gauges whether your PR will get merged.
- **[CodeABC](https://github.com/he-yufeng/CodeABC)** — understand any codebase even if you don't code, built for non-programmers.

## Contributing

Issues and pull requests are welcome!

## License

MIT License
