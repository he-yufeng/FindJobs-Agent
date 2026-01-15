# Project Structure

## Overview
This document describes the complete structure of the NLP project submission.

## Directory Structure

```
code_submission/
├── README.md                          # Main documentation
├── SETUP_GUIDE.md                     # Detailed setup instructions
├── README_API.md                      # API documentation
├── PROJECT_STRUCTURE.md               # This file
├── .gitignore                         # Git ignore rules
│
├── Core Python Modules (Backend)
├── add_tags.py                        # Skill tag augmentation system
├── AI_interviewer.py                  # Adaptive AI interview system
├── tag_rate.py                        # Resume skill tagging & scoring
├── job_agent.py                       # Job structuring & analysis
├── api_server.py                      # Flask backend API server
├── resume_parser.py                   # Resume parsing module
├── job_matcher.py                     # Job matching module
├── interview_agent.py                 # Interview agent module
├── llm_client.py                      # LLM client wrapper
├── llm_utils.py                       # LLM utility functions
│
├── Configuration Files
├── requirements.txt                   # Python dependencies
├── llm_config.json                    # LLM configuration
├── API_key-openai.md.template         # API key template
│
├── Data Files
├── bytedance_jobs.json                # Sample job postings (5.4 MB)
├── tech_taxonomy.json                 # Job family hierarchy cache (28 KB)

Note: all_labels.csv (skill taxonomy) is not included due to privacy concerns.
│
├── scripts/                           # Startup scripts
│   ├── start_linux.sh                # Linux/macOS startup
│   └── start_windows.bat             # Windows startup
│
└── FrontEnd/                          # React frontend application
    ├── src/
    │   ├── App.tsx                   # Main application component
    │   ├── main.tsx                  # Application entry point
    │   ├── index.css                 # Global styles
    │   ├── components/               # React components
    │   │   ├── ResumePage.tsx       # Resume analysis page
    │   │   ├── JobsPage.tsx         # Job matching page
    │   │   ├── InterviewPage.tsx    # AI interview page
    │   │   └── Navigation.tsx       # Navigation component
    │   ├── lib/
    │   │   ├── mockApi.ts           # Mock API for development
    │   │   └── supabase.ts          # Supabase client (optional)
    │   └── types/
    │       └── index.ts              # TypeScript type definitions
    ├── dist/                          # Production build output
    ├── package.json                   # Node.js dependencies
    ├── vite.config.ts                 # Vite configuration
    ├── tsconfig.json                  # TypeScript configuration
    ├── tailwind.config.js             # Tailwind CSS configuration
    └── README.md                      # Frontend documentation
```

## Component Details

### Core Python Modules

#### 1. add_tags.py (Skill Tag Augmentation)
- **Purpose**: Analyze job descriptions to suggest missing skill tags
- **Input**: Skill taxonomy file (not included, user must provide), job descriptions
- **Output**: `new_labels_list.csv`
- **Key Features**:
  - Multi-threaded processing
  - LLM-powered tag suggestion
  - API key rotation support

#### 2. AI_interviewer.py (AI Interview System)
- **Purpose**: Interactive adaptive interview system
- **Key Features**:
  - Adaptive difficulty based on performance
  - Multi-dimensional scoring (0-5 scale)
  - Comprehensive feedback reports
  - Follow-up question generation

#### 3. tag_rate.py (Resume Skill Tagging)
- **Purpose**: Analyze resumes and assign skill tags with scores
- **Input**: User profiles CSV
- **Output**: `ai_user_tags.csv`
- **Key Features**:
  - V4 scoring framework
  - Social network-based user prioritization
  - Dual task system (scoring + augmentation)

#### 4. job_agent.py (Job Structuring)
- **Purpose**: Extract structured information from job postings
- **Input**: `bytedance_jobs.json`
- **Output**: `bytedance_jobs_enriched.csv`
- **Key Features**:
  - Job intensity detection
  - External knowledge retrieval
  - Dynamic job taxonomy generation
  - Skill normalization and review

#### 5. api_server.py (Backend API)
- **Purpose**: Flask-based REST API server
- **Port**: 5000
- **Key Endpoints**:
  - `/api/health` - Health check
  - `/api/resume/upload` - Resume upload
  - `/api/jobs` - Job listings
  - `/api/jobs/match` - Job matching
  - `/api/interview/start` - Start interview
  - `/api/interview/<session_id>/message` - Interview Q&A

#### 6. resume_parser.py
- **Purpose**: Parse PDF resumes and extract information
- **Features**:
  - PDF text extraction
  - Skill tag assignment
  - LLM-powered analysis

#### 7. job_matcher.py
- **Purpose**: Match resumes to job postings
- **Algorithm**: Tag-based matching with scoring

#### 8. interview_agent.py
- **Purpose**: Manage interview sessions
- **Features**:
  - 3-stage interview flow (Greeting → Q&A → Summary)
  - Dynamic question generation
  - Answer evaluation with detailed feedback

#### 9. llm_client.py
- **Purpose**: OpenAI API client wrapper
- **Features**:
  - Temperature control
  - Retry logic with exponential backoff
  - JSON response parsing

#### 10. llm_utils.py
- **Purpose**: LLM utility functions
- **Features**: Common helper functions for LLM operations

### Configuration Files

#### requirements.txt
Python dependencies:
- flask==3.0.0
- flask-cors==4.0.0
- pandas==2.1.4
- requests==2.31.0
- PyPDF2==3.0.1
- urllib3<2

#### llm_config.json
LLM configuration:
```json
{
  "api_key": "your-api-key",
  "model": "gpt-5-mini",
  "api_url": "https://api.openai.com/v1/chat/completions",
  "timeout": 120,
  "max_retry": 3
}
```

#### API_key-openai.md.template
Template for OpenAI API keys. Copy to `API_key-openai.md` and add your keys.

### Data Files

**Note:** `all_labels.csv` (skill taxonomy) is not included in this submission due to privacy concerns. Users need to provide their own skill taxonomy file with the following format:
- `level_3rd`: Job role category
- `skill_type`: Type of skill
- `tags`: Skill tags (pipe-separated)

#### bytedance_jobs.json (5.4 MB)
Sample job postings with fields:
- `job_id`: Unique identifier
- `company_name`: Company name
- `job_title`: Job title
- `category`: Job category
- `location`: Job location
- `job_description`: Description text
- `job_requirements`: Requirements text

#### tech_taxonomy.json (28 KB)
Cached job family hierarchy:
- Level 1: 18-22 major categories
- Level 2: 180-220 specific roles
- Auto-generated by `job_agent.py`

### Frontend Application

#### Technology Stack
- **Framework**: React 18
- **Language**: TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **State Management**: React Hooks

#### Key Components

**ResumePage.tsx**
- Resume upload interface
- Skill analysis display
- PDF file validation

**JobsPage.tsx**
- Job listing display
- Job matching results
- Filter and sort functionality

**InterviewPage.tsx**
- Interactive interview interface
- Real-time Q&A
- Score and feedback display

**Navigation.tsx**
- Application navigation
- Page routing

#### Frontend Structure
```
FrontEnd/
├── src/
│   ├── components/          # React components
│   ├── lib/                # Utility libraries
│   ├── types/              # TypeScript types
│   └── *.tsx               # App entry files
├── dist/                    # Build output
├── package.json            # Dependencies
├── vite.config.ts          # Vite config
└── tsconfig.json           # TypeScript config
```

### Startup Scripts

#### start_linux.sh (Linux/macOS)
- Checks Python 3 installation
- Creates virtual environment
- Installs dependencies
- Starts backend in background
- Starts frontend development server

#### start_windows.bat (Windows)
- Checks Python installation
- Creates virtual environment
- Installs dependencies
- Starts backend in new console
- Starts frontend in new console

## Workflow

### Development Workflow
1. Start backend: `python api_server.py`
2. Start frontend: `cd FrontEnd && npm run dev`
3. Access application at `http://localhost:5173`

### Data Processing Workflow
1. **Skill Augmentation**: `python add_tags.py`
2. **Job Structuring**: `python job_agent.py`
3. **Resume Tagging**: `python tag_rate.py --num-tags 5`
4. **Interactive Interview**: `python AI_interviewer.py`

### API Integration Workflow
```
User → Frontend (React) → Backend API (Flask) → Python Modules (LLM) → OpenAI API
                                              ↓
                                         Data Files (CSV/JSON)
```

## File Sizes
- Total project size: ~7 MB
- Python code: ~150 KB
- Data files: ~6.5 MB
- Frontend code: ~300 KB (excluding node_modules)

## Dependencies

### Python Dependencies (7 packages)
- flask, flask-cors: Web framework
- pandas: Data processing
- requests: HTTP client
- PyPDF2: PDF parsing
- urllib3: HTTP utilities

### Frontend Dependencies (~40 packages)
- react, react-dom: UI framework
- typescript: Type system
- vite: Build tool
- tailwindcss: CSS framework
- Other utilities (see package.json)

## Notes

1. **API Keys**: Required for all LLM functionality
2. **Data Files**: Sample data included, can be replaced with custom data
3. **Frontend**: Can run independently with mock data
4. **Backend**: Stateless API server with in-memory session storage
5. **Production**: Additional configuration needed for production deployment

---

For detailed setup instructions, see `SETUP_GUIDE.md`.
For API documentation, see `README_API.md`.

