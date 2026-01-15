NLP Project – FrontEnd (React + Vite + Tailwind)
=================================================

This is the frontend for the NLP Project. It provides:

- Resume Parsing: upload a PDF resume, preview extracted info and skill scoring.
- Job Matching: list enriched job positions (/api/jobs) and rank them by personalized match score from the backend (/api/jobs/match).
- AI Interview: 3-phase interview flow (Greeting → Q&A(5 rounds) → Summary) backed by the backend interview service.

Prerequisites
-------------
- Node.js 18+ (LTS recommended)
- Running backend service (see project root or `README_API.md`)

Project Setup
-------------
```bash
cd FrontEnd
npm install
```

Development
-----------
Create `.env` in `FrontEnd/` if you want to point to a non-default backend:

```env
# Backend API base (default http://localhost:5000/api if not set)
VitaliApiURL=http://localhost:5000/api
```

Start dev server:
```bash
npm run dev
```

By default, Vite serves at `http://localhost:5173`. The Vite dev server is configured with a proxy for `/api` to `http://localhost:5000`, so you can also omit `VITE_API_URL` during local development.

Build
-----
```bash
npm run build
npm run preview
```

Feature Walkthrough
-------------------
1) Resume Parsing
   - Page: “上传简历”
   - Action: upload a `.pdf` file
   - Calls backend: `POST /api/resume/upload` (multipart form, field `file`)
   - Displays parsed fields: name, email, phone, education, experience
   - Displays skill scoring grouped by category; category “其他” is always rendered at the bottom
   - Stores `resume_id` in `localStorage` for later matching/interview

2) Job Matching
   - Page: “岗位匹配”
   - Loads jobs via `GET /api/jobs`
   - Triggers matching via `POST /api/jobs/match` with `{ "resume_id": "<from localStorage>" }`
   - Ranks jobs: primarily by number of matched tags, secondarily by match score
   - Displays per-job match score badge and required skills

3) AI Interview (3-phase)
   - Page: “AI 智能面试”
   - Phase 1 (Greeting):
       - `POST /api/interview/start` with `{ resume_id?, job_id? }`
       - Backend responds with: `greeting` and `self_intro` (no question yet), and sets session `phase=greeting`
   - Phase 2 (Q&A):
       - After the first user answer, the frontend calls `POST /api/interview/{session_id}/message`
       - Backend transitions to `phase=qa`, returns “第1题”，then expects 5 rounds total
       - Each subsequent user answer triggers scoring of previous question and returns the next question, until 5 questions are done
   - Phase 3 (Summary):
       - After 5 Q&A rounds, backend returns a summary message with `final_feedback` and `average_score`, `phase=summary`
       - The UI may show a “Restart Interview” action

Configuration & Notes
---------------------
- Make sure `api_server.py` is running at `http://localhost:5000` (or adjust `VITE_API_URL`)
- Ensure backend has required files:
  - `API_key-openai.md` with OpenAI keys (see backend README)
  - `all_labels.csv`
  - `bytedance_jobs_enriched.csv` (produced by `job_agent.py`)
- The frontend uses `FrontEnd/src/lib/mockApi.ts` as a thin wrapper over the backend endpoints (no local mocks in production)

Key Commands
------------
- `npm run dev` — start dev server
- `npm run build` — production build
- `npm run preview` — preview production build

Project Structure (Frontend)
---------------------------
```
FrontEnd/
  src/
    components/
      ResumePage.tsx       # Resume upload & skill display
      JobsPage.tsx         # Job list & match scores
      InterviewPage.tsx    # 3-phase AI interview UI
    lib/
      mockApi.ts           # API calls to backend
      supabase.ts          # (optional) sample integration scaffold
    types/
      index.ts             # Shared TS types
  vite.config.ts
  package.json
  README.md               # (this file)
```

Troubleshooting
---------------
- “Network error” on API calls: confirm backend is running and `VITE_API_URL`/proxy is correct.
- CORS: backend enables CORS via `flask-cors`; ensure it’s installed and active.
- Skill categories not appearing: ensure backend successfully parsed resume and returned `skills` with `category` fields.
