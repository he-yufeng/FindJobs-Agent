# NLP Project - Technical Documentation

This repository contains four intelligent systems powered by Large Language Models (LLMs) for professional skill analysis, interview automation, and job structuring.

---

## 📋 Table of Contents

1. [add_tags.py - Skill Tag Augmentation System](#1-add_tagspy---skill-tag-augmentation-system)
2. [AI_interviewer.py - Adaptive AI Interview System](#2-ai_interviewerpy---adaptive-ai-interview-system)
3. [tag_rate.py - Resume Skill Tagging & Scoring System](#3-tag_ratepy---resume-skill-tagging--scoring-system)
4. [job_agent.py - Job Structuring & Analysis System](#4-job_agentpy---job-structuring--analysis-system)

---

## 1. add_tags.py - Skill Tag Augmentation System

### 🎯 Overview
An intelligent system that analyzes existing skill tag lists and real-world job descriptions to identify and recommend new, important skill tags that are missing from the current taxonomy.

### 🏗️ Technical Architecture

#### Core Components

**1. API Key Manager**
- Implements round-robin API key rotation
- Supports multiple OpenAI API keys for load balancing
- Thread-safe key polling mechanism

**2. Data Processing Pipeline**
```
Load Data → Aggregate Descriptions → Group by Category → LLM Analysis → Output Results
```

**3. LLM Interaction Module**
- Model: `gpt-5-mini`
- Temperature: Default (model-dependent)
- Timeout: 90 seconds
- Max retries: 3 with exponential backoff

**4. Prompt Engineering**
```python
System Role: Top-tier industry skill analysis expert
Core Task: Identify missing but critical skills
Constraints:
  - No duplication with existing tags
  - Strict relevance to skill type
  - Naming consistency with existing tags
  - Maximum 3 new tags, not exceeding half of existing count
Output Format: Strict JSON with "add" key
```

### 📦 Dependencies
```python
- pandas: Data processing
- requests: API communication
- json: Response parsing
- concurrent.futures: Parallel processing
```

### ⚙️ Configuration

**File Paths:**
```python
TAGS_CSV = "all_labels copy.csv"          # Input: Existing tags
USER_DATA_CSV = "merged_user_descriptions.csv"  # Input: Job descriptions
OUTPUT_CSV = "new_labels_list.csv"        # Output: Augmented tags
API_KEY_FILE = "API_key-openai.md"               # API keys file
```

**API Settings:**
```python
API_URL = "https://api.openai.com/v1/chat/completions"
MODEL_NAME = "gpt-5-mini"
TIMEOUT = 90
MAX_RETRY = 3
MAX_WORKERS = min(len(API_KEYS), 10)
```

### 📊 Input Format

**all_labels copy.csv:**
```csv
level_3rd,skill_type,tags
Software Engineer,Technical Skills,Python|_|Java|_|Docker
Product Manager,Product Design,User Research|_|Prototyping
```

**merged_user_descriptions.csv:**
```csv
exp_type,work_lv3_name,work_description
WORK,Software Engineer,Developed microservices using Go and Kubernetes...
WORK,Product Manager,Led product discovery with 50+ user interviews...
```

### 🚀 Usage

**Basic Execution:**
```bash
python add_tags.py
```

**API Key Configuration (API_key-openai.md):**
```
# OpenAI API Keys
user1 sk-proj-xxxxxxxxxxxxx
user2 sk-proj-yyyyyyyyyyyyy
user3 "sk-proj-zzzzzzzzzzzzz"
```

### 📤 Output Format

**new_labels_list.csv:**
```csv
level_3rd,skill_type,original_cnt,add_cnt,original_tags,suggested_add_tags
Software Engineer,Technical Skills,5,2,Python|_|Java|_|Docker|_|...,Kubernetes|_|Go
Product Manager,Product Design,8,1,User Research|_|Prototyping|_|...,A/B Testing
```

### 🔧 Key Features

1. **Intelligent Aggregation**: Combines job descriptions by role category with 4000-char limit
2. **Parallel Processing**: Multi-threaded execution with configurable worker count
3. **Context-Aware Analysis**: LLM considers real-world job examples
4. **Strict Validation**: JSON parsing with fallback mechanisms
5. **Encoding Robustness**: Multi-encoding support (utf-8, gbk, gb2312, etc.)

### ⚠️ Important Notes

- **Rate Limiting**: Automatic exponential backoff on API errors
- **Token Limits**: Job descriptions truncated to 4000 characters per role
- **Output Validation**: Only valid JSON responses are accepted
- **Duplicate Prevention**: System ensures no overlap with existing tags

---

## 2. AI_interviewer.py - Adaptive AI Interview System

### 🎯 Overview
An intelligent interview system that dynamically generates questions, evaluates answers, provides feedback, and adapts difficulty based on candidate performance.

### 🏗️ Technical Architecture

#### Core Components

**1. LLMClient**
```python
- Model Support: gpt-5-mini, gpt-4o-mini (temperature-restricted), others
- Temperature: 0.7 (for generative tasks), 0.2 (for structured tasks)
- Auto-detection: Handles temperature unsupported models
- Response Modes: Text generation, JSON generation
```

**2. InterviewModule**
```python
generate_questions():
  - Adaptive difficulty based on performance history
  - 3-5 subjective questions per session
  - Includes reference answers, thinking guides, grading rubrics

grade_answer():
  - 0-5 point scale
  - Multi-dimensional scoring (understanding, logic, feasibility, depth, communication)
  - Automatic follow-up detection

generate_followup():
  - Context-aware clarification questions
  - Friendly, guiding tone
  - Max 30 characters
```

**3. InterviewOrchestrator**
```python
Workflow:
  1. User inputs: domain, skill type, core skill
  2. Generate opening statement
  3. Initial question batch (3 questions)
  4. Adaptive question generation based on performance
  5. Grading with optional follow-ups
  6. Final comprehensive report
```

### 📦 Dependencies
```python
- openai: Official OpenAI Python client
- json: Structured data handling
- logging: Comprehensive logging
- dataclasses: Type-safe data structures
```

### ⚙️ Configuration

**Model Settings:**
```python
MODEL = 'gpt-5-mini'
TIMEOUT_S = 180
MAX_RETRY = 3
TEMPERATURE = 0.7
```

**Difficulty Adaptation:**
```python
if avg_score >= 4.0:
    → Generate harder questions (up to 5 total)
elif avg_score <= 2.0:
    → Generate easier questions (minimum 2 total)
else:
    → Maintain standard difficulty
```

### 🚀 Usage

**Basic Execution:**
```bash
python AI_interviewer.py
```

**Interactive Flow:**
```
1. Input职业领域 (e.g., "软件工程师")
2. Input技能类型 (e.g., "软件开发")
3. Input核心技能 (e.g., "大模型Agent开发")
4. Answer questions (multi-line input, end with 'END')
5. Receive scores and feedback
6. Answer optional follow-ups
7. Get final comprehensive report
```

### 📊 Question Structure

**JSON Schema:**
```json
{
  "questions": [
    {
      "question_type": "subjective",
      "question": "Design a document Q&A Agent...",
      "difficulty": "medium",
      "reference_answer": "Should include retrieval, LLM reasoning...",
      "thinking_guide": "Consider scalability and error handling...",
      "grading_rubric": "0: No answer\n1: Misunderstands requirements\n..."
    }
  ]
}
```

### 📈 Scoring Dimensions

1. **Problem Understanding** (0-5): Accuracy in identifying requirements
2. **Logical Structure** (0-5): Coherence and organization
3. **Solution Feasibility** (0-5): Practicality and engineering constraints
4. **Detail Depth** (0-5): Specificity and implementation details
5. **Communication** (0-5): Clarity and professionalism

### 📤 Final Report Structure

```
==================================================
面试结束 - 综合反馈报告
==================================================
最终平均得分: 3.80 / 5.00
表现趋势: 表现稳定

总体评价（约120字）
[Comprehensive assessment...]

亮点分析
- [Strength 1 with specific examples]
- [Strength 2 with specific examples]

改进建议（优先级顺序，含可执行步骤）
1) [High priority improvement with action steps]
2) [Second priority with action steps]

能力画像（简要）
[Candidate profile summary]

学习建议（可操作）
1) [Specific learning recommendation]
2) [Practice exercise recommendation]

总评语
[Encouraging closing remarks]
==================================================
```

### 🔧 Key Features

1. **Adaptive Difficulty**: Questions adjust based on rolling average score
2. **Smart Follow-ups**: System detects when clarification needed
3. **Comprehensive Rubrics**: Each question has detailed 0-5 scoring anchors
4. **Multi-line Input**: Supports complex, formatted answers
5. **Trend Analysis**: Tracks performance trajectory (improving/declining/stable)
6. **Actionable Feedback**: Specific, implementable improvement suggestions

### ⚠️ Important Notes

- **API Key Rotation**: Automatically cycles through multiple keys
- **Temperature Compatibility**: Auto-detects model temperature support
- **Session State**: Maintains interview history for context
- **Retry Logic**: Exponential backoff with jitter on failures
- **Input Validation**: Handles empty/invalid responses gracefully

---

## 3. tag_rate.py - Resume Skill Tagging & Scoring System

### 🎯 Overview
A sophisticated system that uses LLM to analyze user resumes, assign skill tags from an official taxonomy, score proficiency levels (1-5), and augment missing skills—all based on rigorous scoring standards.

### 🏗️ Technical Architecture

#### Core Components

**1. APIKeyManager**
```python
- Thread-safe key rotation
- Automatic load balancing
- Supports 10+ concurrent API keys
```

**2. Data Processing Pipeline**
```
Load Data → Calculate User Relationships → Sort by Network Size → 
Process Top N Users → Score Tags → Augment Missing Tags → Save Results
```

**3. Scoring Framework (V4)**

**Anchor-Based Evaluation:**
```
Base Score: 3 (Proficient)
  ↓
Downgrade Rules (MANDATORY):
  - Score 2: Assisted/participation tasks only, lacking independent evidence
  - Score 1: Mentioned only, no project evidence

Upgrade Rules (STRICT, OPTIONAL):
  - Score 4: Advanced leadership, measurable impact, senior role at top companies
  - Score 5: Industry expert, executive role, major open-source/academic contributions
```

**Background Factors Checklist:**
```python
Education:
  - PhD > Master > Bachelor
  - Top 50 global / C9 > 985/211 > Regular

Work Experience:
  - Top companies (FAANG, BAT) > Known > SME
  - 5+ years for "Advanced", 10+ years for "Expert"
  - Director/Chief > Manager/Senior > Junior
```

**4. Task Execution**

**Task 1: Score Existing Tags**
```python
Input: Tags without scores (score=0)
Process: LLM evaluates based on resume
Output: Tags with 1-5 scores, source='AI'
```

**Task 2: Augment Missing Tags**
```python
Input: Target count not met
Process: LLM selects from candidate pool
Output: New tags with scores, source='AI'
Constraint: No duplication, exact match required
```

### 📦 Dependencies
```python
- pandas: DataFrame operations
- requests: HTTP API calls
- argparse: CLI argument parsing
- concurrent.futures: Parallel processing
```

### ⚙️ Configuration

**Global Settings:**
```python
API_URL = 'https://api.openai.com/v1/chat/completions'
MODEL = 'gpt-5-mini'
TIMEOUT_S = 120
MAX_RETRY = 3
TOP_N = 500  # Top users to process
MAX_WORKERS = 10  # Parallel threads
```

**File Paths:**
```python
USER_PROFILE_CSV = 'user_descriptions copy.csv'
OFFICIAL_TAGS_CSV = 'all_labels.csv'
API_KEY_FILE = 'API_key-openai.md'
OUTPUT_CSV = 'ai_user_tags.csv'  # Both input and output
RELATIONSHIP_CSV = 'user_relationship_sorted.csv'
```

### 📊 Input Format

**user_descriptions copy.csv:**
```csv
uid,exp_type,work_lv3_name,work_company,work_position,work_start_date,work_end_date,work_description,edu_school,edu_major
12345,WORK,Software Engineer,Google,Senior SWE,2020-01,至今,Led ML infrastructure team...,Stanford,Computer Science
12345,EDU,,,,,,,Stanford,Computer Science
```

**all_labels.csv:**
```csv
level_3rd,skill_type,tags
Software Engineer,Programming Languages,Python|_|Java|_|Go|_|C++
Data Scientist,Machine Learning,Deep Learning|_|NLP|_|Computer Vision
```

**ai_user_tags.csv (existing, optional):**
```csv
uid,tags
12345,Python , 0 , HM | Java , 0 , HM | TensorFlow , 3 , AI
67890,Product Design , 0 , HM
```

### 🚀 Usage

**Basic Execution:**
```bash
python tag_rate.py
```

**Custom Target Tag Count:**
```bash
python tag_rate.py --num-tags 8
```

**CLI Arguments:**
```bash
-n, --num-tags    Target number of tags per user (default: 5)
```

### 📤 Output Format

**ai_user_tags.csv:**
```csv
uid,tags
12345,Python , 4 , AI | Machine Learning , 4 , AI | Docker , 3 , AI | Kubernetes , 3 , AI | TensorFlow , 4 , AI
67890,Product Design , 3 , AI | User Research , 3 , AI | Prototyping , 2 , AI | A/B Testing , 3 , AI | Figma , 3 , AI
```

**Tag Format:**
```
<tag_name> , <score_1-5> , <source_AI|HM> | <next_tag> | ...
```

### 🔧 Key Features

1. **Social Network Sorting**: Prioritizes users with most connections (colleagues, alumni)
2. **Incremental Processing**: Preserves existing scored tags, only processes what's needed
3. **Dual Task System**: 
   - Scores unscored tags
   - Augments missing tags to target count
4. **Rigorous Scoring**: V4 framework with mandatory downgrade and strict upgrade rules
5. **Context-Aware Candidates**: Matches tags to user's work categories (level_3rd)
6. **Parallel Execution**: Multi-threaded with 10 concurrent workers
7. **Resume Construction**: Aggregates work/education history into coherent profile text

### ⚠️ Important Notes

- **User Relationship Calculation**: 
  - Current colleagues (same company, currently employed)
  - Former colleagues (same company, any time)
  - Alumni (same school)
- **Candidate Pool**: Tags filtered by user's work_lv3_name categories
- **LLM Output Parsing**: Strict regex `([^:：\s]+?)\s*[:：]\s*([1-5])` with validation
- **Error Handling**: Individual user failures don't stop batch processing
- **Data Preservation**: Users not in Top N retain their existing tags
- **Encoding Robustness**: Supports utf-8, gbk, gb2312, gb18030, utf-8-sig, latin1

---

## 4. job_agent.py - Job Structuring & Analysis System

### 🎯 Overview
An advanced system that analyzes job postings to extract structured information including education requirements, major requirements, skill tags with proficiency scores, and job family classification—while detecting job intensity signals to calibrate skill scoring.

### 🏗️ Technical Architecture

#### Core Components

**1. SkillRepository**
```python
- Loads all_labels.csv skill taxonomy
- Fuzzy matching between job text and level_3rd categories
- Dynamic candidate selection (top 12 categories, ~80 skills per job)
- Direct text matching + fallback pool (150 common skills)
```

**2. TaxonomyManager**
```python
- Constructs 180-220 L2 job roles across 18-22 L1 categories
- Uses user_descriptions.csv for real-world job frequency
- LLM-generated hierarchy with keyword indexing
- Persistent caching to tech_taxonomy.json
```

**3. JobSignalAnalyzer**
```python
Intensity Signals:
  - PhD degree programs
  - Flagship/talent programs
  - International labs
  - Top-tier conferences (ACL, NeurIPS, CVPR, etc.)
  - Frontier LLM/Agent research

Intensity Levels:
  - flagship_research (score ≥9, base=5)
  - research (score ≥6, base=4)
  - advanced (score ≥3, base=3)
  - standard (score ≥0, base=3)
```

**4. KnowledgeRetriever**
```python
- Extracts program/lab names from job text
- Fetches background context via DuckDuckGo Instant API
- Caches results to program_context_cache.json
- Provides additional context to LLM for better scoring
```

**5. SkillNormalizer**
```python
- Replaces generic skills (AI, 技术, 数学) with specific alternatives
- Validates against official skill taxonomy
- Removes low-information duplicates
```

**6. SkillReviewAgent**
```python
- Post-processing quality assurance
- For high-intensity jobs (base ≥4), reviews low scores
- Uses LLM to adjust scores upward if justified by signals
- Ensures alignment with job requirements
```

**7. JobAgent (Main Orchestrator)**
```python
Workflow per job:
  1. Extract job text (title, description, requirements)
  2. Get candidate skills from SkillRepository
  3. Get job family candidates from TaxonomyManager
  4. Analyze job intensity (signals)
  5. Retrieve program context (if applicable)
  6. Call LLM with comprehensive prompt
  7. Parse & validate LLM output
  8. Normalize & select skills (3-10)
  9. Review skills based on intensity
  10. Format and return structured result
```

### 📦 Dependencies
```python
- pandas: Data manipulation
- requests: API communication
- argparse: CLI parsing
- difflib: Sequence matching for fuzzy search
- concurrent.futures: Parallel job processing
- tag_rate: Imports APIKeyManager, COMMON_SCORING_RULES_V4, format_tags_for_csv
```

### ⚙️ Configuration

**API Settings:**
```python
API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-5-mini"
REQUEST_TIMEOUT = 120
MAX_LLM_RETRY = 3
MAX_WORKERS = 10
```

**Signal Detection:**
```python
SIGNAL_RULES = [
  {"label": "博士学位", "weight": 4, "tier": "research"},
  {"label": "旗舰/人才计划", "weight": 3, "tier": "flagship"},
  {"label": "国际/跨国实验室", "weight": 2, "tier": "research"},
  {"label": "顶级会议/科研成果", "weight": 3, "tier": "research"},
  {"label": "前沿大模型/Agent研究", "weight": 2, "tier": "research"}
]
```

**File Paths:**
```python
DEFAULT_JOBS_FILE = "bytedance_jobs copy.json"
DEFAULT_LABELS_FILE = "all_labels.csv"
DEFAULT_USER_DESC_FILE = "user_descriptions.csv"
DEFAULT_TAXONOMY_FILE = "tech_taxonomy.json"
DEFAULT_OUTPUT_FILE = "bytedance_jobs_enriched.csv"
DEFAULT_API_KEY_FILE = "API_key-openai.md"
PROGRAM_CACHE_FILE = "program_context_cache.json"
```

### 📊 Input Format

**bytedance_jobs copy.json:**
```json
[
  {
    "job_id": "JOB001",
    "company_name": "ByteDance",
    "job_title": "大模型 Agent 研究员 (Top Seed Program)",
    "category": "算法",
    "location": "北京",
    "special_program": "Top Seed Program",
    "job_description": "负责通用大模型 Agent 技术研发...",
    "job_requirements": "博士学位，发表过 NeurIPS/ICLR 论文...",
    "apply_url": "https://..."
  }
]
```

**all_labels.csv:**
```csv
level_3rd,skill_type,tags
算法工程师,机器学习,深度学习|_|强化学习|_|NLP|_|计算机视觉
```

**user_descriptions.csv (for taxonomy construction):**
```csv
uid,exp_type,work_lv3_name
1,WORK,搜广推算法工程师
2,WORK,Java后端开发
3,WORK,产品经理
```

### 🚀 Usage

**Basic Execution:**
```bash
python job_agent.py
```

**Full Parameter Specification:**
```bash
python job_agent.py \
  --jobs-file bytedance_jobs.json \
  --output-file jobs_structured.csv \
  --taxonomy-file tech_taxonomy.json \
  --min-skills 3 \
  --max-skills 10 \
  --max-workers 10 \
  --model gpt-5-mini
```

**Force Rebuild Taxonomy:**
```bash
python job_agent.py --rebuild-taxonomy
```

**CLI Arguments:**
```bash
--jobs-file PATH         Input job JSON file
--labels-file PATH       Skill taxonomy CSV
--user-desc-file PATH    User descriptions for taxonomy
--taxonomy-file PATH     Job family taxonomy JSON (cache)
--output-file PATH       Output CSV file
--api-key-file PATH      API keys file
--model STR              LLM model name (default: gpt-5-mini)
--min-skills INT         Minimum skills per job (default: 3)
--max-skills INT         Maximum skills per job (default: 10)
--max-workers INT        Parallel threads (default: 10)
--rebuild-taxonomy       Force rebuild job taxonomy
--verbose                Enable debug logging
```

### 📤 Output Format

**bytedance_jobs_enriched.csv:**
```csv
job_id,company_name,job_title,category,location,special_program,job_description,job_requirements,apply_url,min_degree,degree_priority,major_requirement_text,major_requirement_priority,skill_tags,job_level1,job_level2,llm_raw_json
JOB001,ByteDance,大模型Agent研究员,算法,北京,Top Seed Program,[original text],[original text],https://...,博士,必须,计算机科学、人工智能、NLP相关专业,必须,深度学习 , 5 , AI | 强化学习 , 4 , AI | NLP , 5 , AI | PyTorch , 4 , AI | LangChain , 3 , AI,算法,大模型研究,{...}
```

**Skill Tags Format:**
```
<skill> , <score_1-5> , AI | <next_skill> , <score> , AI | ...
```

### 🔧 Key Features

1. **Intelligent Skill Matching**: 
   - Fuzzy matching between job text and skill categories
   - Direct text search within job description
   - Global fallback pool for edge cases

2. **Dynamic Job Taxonomy**:
   - Auto-generates 180-220 L2 roles from real job data
   - Keyword-based matching with confidence scoring
   - One-time LLM construction with persistent caching

3. **Job Intensity Detection**:
   - 5 signal types with weighted scoring
   - Automatic base score adjustment (3→4→5)
   - Signal-aware skill scoring

4. **External Knowledge Retrieval**:
   - Recognizes program/lab names
   - Fetches context from DuckDuckGo
   - Enriches LLM prompt with background info

5. **Quality Assurance**:
   - SkillNormalizer removes generic terms
   - SkillReviewAgent validates high-intensity jobs
   - Ensures 3-10 skills per job with fallback

6. **Parallel Processing**:
   - Multi-threaded job processing
   - Thread-safe API key rotation
   - Progress tracking and error isolation

### 📋 LLM Prompt Structure

```
### System Prompt
- Role: 资深人力与技能分析专家
- Scoring Framework: COMMON_SCORING_RULES_V4 (from tag_rate.py)
- Output: Strict JSON format

### User Prompt Components
1. Job Information
   - Company, title, category, location, program
   - Description & requirements

2. Strength Assessment
   - Intensity level & base score
   - Detected signals with explanations

3. External Knowledge
   - Program/lab background summaries

4. Candidate Skills
   - 3-10 skills from SkillRepository
   - Must select from this list exactly

5. Job Family Candidates
   - Top 4 L1 categories with L2 options
   - Max 40 L2 roles

6. Output Schema
   {
     "min_degree": {"degree": "本科|硕士|博士|大专", "priority": "必须|优先"},
     "major_requirement": {"text": "...", "priority": "必须|优先"},
     "skills": [{"name": "技能名", "score": 1-5}, ...],
     "job_family": {"level1": "...", "level2": "..."}
   }
```

### ⚠️ Important Notes

- **Taxonomy Construction**: First run may take 30-60 seconds to build job taxonomy
- **Program Context**: Requires internet access for DuckDuckGo lookups
- **Skill Validation**: All skills must exist in all_labels.csv
- **Scoring Alignment**: Uses same V4 framework as tag_rate.py
- **Error Handling**: Individual job failures don't stop batch processing
- **Cache Management**: 
  - tech_taxonomy.json: Job family hierarchy
  - program_context_cache.json: External knowledge
- **Performance**: ~10-15 seconds per job with API calls

---

## 🔑 Common Setup

### API Key Configuration

Create `API_key-openai.md` in the project root:

```markdown
# OpenAI API Keys

alice sk-proj-abc123...
bob "sk-proj-def456..."
charlie sk-proj-ghi789...
```

### File Structure
```
project_root/
├── add_tags.py
├── AI_interviewer.py
├── tag_rate.py
├── job_agent.py
├── API_key-openai.md
├── all_labels.csv
├── all_labels copy.csv
├── user_descriptions.csv
├── user_descriptions copy.csv
├── bytedance_jobs.json
├── bytedance_jobs copy.json
├── ai_user_tags.csv (generated)
├── new_labels_list.csv (generated)
├── bytedance_jobs_enriched.csv (generated)
├── user_relationship_sorted.csv (generated)
├── tech_taxonomy.json (generated)
└── program_context_cache.json (generated)
```

### Python Environment
```bash
pip install pandas requests openai
```

---

## 📞 Support

For issues or questions, please refer to the source code comments or contact the development team.

---

## 🚀 Quick Start (One‑click scripts)

This project includes helper scripts to start both Backend (Flask) and FrontEnd (Vite/React) with dependency installation.

### Windows (PowerShell / CMD)
```
scripts\\start_windows.bat
```
What it does:
- Checks for Python, creates `.venv`, installs `requirements.txt`
- Launches `api_server.py` in a new console (http://localhost:5000)
- Ensures `npm` is available (prints a hint if missing), installs FrontEnd deps, launches `npm run dev` in a new console (http://localhost:5173)

### Linux / macOS (Bash)
```bash
chmod +x scripts/start_linux.sh
./scripts/start_linux.sh
```
What it does:
- Checks for Python 3, creates `.venv`, installs `requirements.txt`
- Starts backend in background (logs at `backend.log`)
- Checks for `npm` (prints install hint if missing), installs FrontEnd deps, runs `npm run dev`

Notes:
- If `npm` is not installed, please install Node.js LTS (https://nodejs.org) or via nvm, then re-run the script.
- Ensure `API_key-openai.md`, `all_labels.csv`, and `bytedance_jobs_enriched.csv` exist in the project root (see `README_API.md`).

---

**Last Updated:** 2025-11-15

