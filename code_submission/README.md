# NLP Final Project - Code Submission

## Project Overview

This project implements an intelligent job-matching and interview system powered by Large Language Models (LLMs). It consists of four main components:

1. **Skill Tag Augmentation System** (`add_tags.py`)
2. **Adaptive AI Interview System** (`AI_interviewer.py`)
3. **Resume Skill Tagging & Scoring System** (`tag_rate.py`)
4. **Job Structuring & Analysis System** (`job_agent.py`)

Additionally, the project includes a full-stack web application with:
- **Backend API Server** (`api_server.py`) - Flask-based REST API
- **Frontend Application** (`FrontEnd/`) - React + TypeScript + Vite

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 16+ (for frontend)
- OpenAI API Key (required for LLM functionality)

### Setup

1. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure API Keys:**

Create `API_key-openai.md` in the project root:
```
# OpenAI API Keys
user1 sk-proj-xxxxxxxxxxxxx
user2 sk-proj-yyyyyyyyyyyyy
```

Update `llm_config.json` with your API key:
```json
{
  "api_key": "your-api-key-here",
  "model": "gpt-5-mini",
  "api_url": "https://api.openai.com/v1/chat/completions"
}
```

3. **Run with One-Click Scripts:**

**Windows:**
```bash
scripts\start_windows.bat
```

**Linux/macOS:**
```bash
chmod +x scripts/start_linux.sh
./scripts/start_linux.sh
```

This will:
- Start the backend API server at `http://localhost:5000`
- Start the frontend development server at `http://localhost:5173`

### Manual Startup

**Backend:**
```bash
python api_server.py
```

**Frontend:**
```bash
cd FrontEnd
npm install
npm run dev
```

## Core Components

### 1. Skill Tag Augmentation (`add_tags.py`)

Analyzes job descriptions and existing skill taxonomy to suggest new skill tags.

```bash
python add_tags.py
```

**Input:** Job descriptions (skill taxonomy file required but not included due to privacy)
**Output:** `new_labels_list.csv`

### 2. AI Interview System (`AI_interviewer.py`)

Interactive interview system with adaptive difficulty.

```bash
python AI_interviewer.py
```

Features:
- Adaptive question generation based on performance
- Multi-dimensional scoring (0-5 scale)
- Comprehensive feedback reports

### 3. Resume Skill Tagging (`tag_rate.py`)

Analyzes resumes and assigns skill tags with proficiency scores.

```bash
python tag_rate.py --num-tags 5
```

**Input:** User profiles, skill taxonomy
**Output:** `ai_user_tags.csv`

### 4. Job Structuring (`job_agent.py`)

Extracts structured information from job postings.

```bash
python job_agent.py
```

**Input:** `bytedance_jobs.json`
**Output:** `bytedance_jobs_enriched.csv`

Features:
- Education and major requirement extraction
- Skill tagging with proficiency scores
- Job family classification
- Job intensity detection

## Web Application

### Backend API Endpoints

- `POST /api/resume/upload` - Upload and parse resume
- `POST /api/resume/analyze` - Analyze resume skills
- `GET /api/jobs` - Get matched job listings
- `POST /api/interview/start` - Start interview session
- `POST /api/interview/answer` - Submit answer and get next question

### Frontend Features

1. **Resume Analysis Page** - Upload PDF resume for skill analysis
2. **Job Matching Page** - View matched jobs based on skills
3. **AI Interview Page** - Interactive interview experience

## File Structure

```
code_submission/
├── add_tags.py              # Skill augmentation system
├── AI_interviewer.py        # Interview system
├── tag_rate.py              # Resume tagging system
├── job_agent.py             # Job structuring system
├── api_server.py            # Flask backend server
├── resume_parser.py         # Resume parsing module
├── job_matcher.py           # Job matching module
├── interview_agent.py       # Interview agent module
├── llm_client.py            # LLM client wrapper
├── llm_utils.py             # LLM utilities
├── requirements.txt         # Python dependencies
├── llm_config.json          # LLM configuration
├── tech_taxonomy.json       # Job taxonomy cache
├── bytedance_jobs.json      # Sample job data
├── scripts/                 # Startup scripts
│   ├── start_linux.sh
│   └── start_windows.bat
└── FrontEnd/                # React frontend
    ├── src/
    ├── package.json
    └── vite.config.ts
```

## Key Technologies

**Backend:**
- Python 3.8+
- Flask (Web framework)
- Pandas (Data processing)
- OpenAI API (LLM integration)

**Frontend:**
- React 18
- TypeScript
- Vite (Build tool)
- Tailwind CSS (Styling)

## Configuration Files

### llm_config.json
```json
{
  "api_key": "your-api-key",
  "model": "gpt-5-mini",
  "api_url": "https://api.openai.com/v1/chat/completions",
  "timeout": 120,
  "max_retry": 3
}
```

### Data Files

- **bytedance_jobs.json** - Sample job postings
- **tech_taxonomy.json** - Cached job family hierarchy (auto-generated)

**Note:** Skill taxonomy file (`all_labels.csv`) is not included due to privacy concerns. Users need to provide their own skill taxonomy file.

## Important Notes

1. **API Keys:** Required for all LLM-powered features. Configure in `API_key-openai.md` or `llm_config.json`
2. **Data Files:** Sample data files are included. Replace with your own data as needed.
3. **Model:** Default model is `gpt-5-mini`. Change in configuration files if using different models.
4. **Timeout:** API requests have 120s timeout. Adjust in configuration if needed.
5. **Parallel Processing:** Default 10 concurrent workers. Adjust based on API rate limits.

## Testing

Run the full system test:
```bash
python test.py
```

## Troubleshooting

**Issue: API Key Error**
- Ensure `API_key-openai.md` or `llm_config.json` contains valid API keys

**Issue: Module Not Found**
- Run `pip install -r requirements.txt`

**Issue: Frontend Not Starting**
- Ensure Node.js is installed
- Run `npm install` in FrontEnd directory

**Issue: CORS Error**
- Backend enables CORS by default. Check if backend is running on port 5000

## Contact

For technical questions or issues, please refer to the detailed documentation in individual Python files or contact the development team.

---

**Last Updated:** November 2025

