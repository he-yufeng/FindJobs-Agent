# Setup Guide for NLP Project

This guide provides detailed setup instructions for running the NLP project.

## Prerequisites

- **Python**: 3.8 or higher
- **Node.js**: 16 or higher (for frontend)
- **OpenAI API Key**: Required for LLM functionality
- **Git**: For cloning the repository (optional)

## Step-by-Step Setup

### Step 1: Python Environment Setup

1. **Create virtual environment** (recommended):
```bash
python -m venv .venv
```

2. **Activate virtual environment**:

- **Windows**:
  ```bash
  .venv\Scripts\activate
  ```

- **Linux/macOS**:
  ```bash
  source .venv/bin/activate
  ```

3. **Install Python dependencies**:
```bash
pip install -r requirements.txt
```

### Step 2: API Key Configuration

**Option A: Using API_key-openai.md (Recommended for multiple keys)**

1. Copy the template:
```bash
cp API_key-openai.md.template API_key-openai.md
```

2. Edit `API_key-openai.md` and add your API keys:
```
# OpenAI API Keys
user1 sk-proj-xxxxxxxxxxxxx
user2 sk-proj-yyyyyyyyyyyyy
```

**Option B: Using llm_config.json**

Edit `llm_config.json`:
```json
{
  "api_key": "sk-proj-your-actual-api-key",
  "model": "gpt-5-mini",
  "api_url": "https://api.openai.com/v1/chat/completions",
  "timeout": 120,
  "max_retry": 3
}
```

### Step 3: Frontend Setup

1. **Navigate to frontend directory**:
```bash
cd FrontEnd
```

2. **Install Node.js dependencies**:
```bash
npm install
```

3. **Return to project root**:
```bash
cd ..
```

### Step 4: Run the Application

**Option A: Use one-click startup scripts (Recommended)**

- **Windows**:
  ```bash
  scripts\start_windows.bat
  ```

- **Linux/macOS**:
  ```bash
  chmod +x scripts/start_linux.sh
  ./scripts/start_linux.sh
  ```

**Option B: Manual startup**

1. **Start Backend** (Terminal 1):
```bash
python api_server.py
```
Backend will run at `http://localhost:5000`

2. **Start Frontend** (Terminal 2):
```bash
cd FrontEnd
npm run dev
```
Frontend will run at `http://localhost:5173`

## Testing Individual Components

### Test Resume Skill Tagging
```bash
python tag_rate.py --num-tags 5
```

### Test Job Structuring
```bash
python job_agent.py --verbose
```

### Test AI Interview
```bash
python AI_interviewer.py
```

### Test Skill Augmentation
```bash
python add_tags.py
```

## Verification

1. **Check Backend**:
   - Open browser to `http://localhost:5000/api/health`
   - Should return: `{"status": "ok"}`

2. **Check Frontend**:
   - Open browser to `http://localhost:5173`
   - Should see the application interface

3. **Test Resume Upload**:
   - Navigate to Resume Analysis page
   - Upload a PDF resume
   - Verify skill analysis results

## Common Issues and Solutions

### Issue 1: Python Module Not Found
```
ModuleNotFoundError: No module named 'flask'
```

**Solution:**
```bash
pip install -r requirements.txt
```

### Issue 2: OpenAI API Error
```
Error: Invalid API key
```

**Solution:**
- Verify API key is correct in `API_key-openai.md` or `llm_config.json`
- Ensure API key has sufficient credits
- Check API key format (should start with `sk-proj-` or `sk-`)

### Issue 3: Port Already in Use
```
OSError: [Errno 48] Address already in use
```

**Solution:**
- Backend (port 5000):
  ```bash
  # Find process
  lsof -i :5000  # macOS/Linux
  netstat -ano | findstr :5000  # Windows
  
  # Kill process
  kill -9 <PID>  # macOS/Linux
  taskkill /PID <PID> /F  # Windows
  ```

- Frontend (port 5173): Same steps but replace 5000 with 5173

### Issue 4: CORS Error in Browser
```
Access to fetch at 'http://localhost:5000' from origin 'http://localhost:5173' has been blocked by CORS policy
```

**Solution:**
- Ensure backend server is running
- Backend automatically enables CORS
- Try restarting both frontend and backend

### Issue 5: Frontend Dependencies Error
```
npm ERR! ERESOLVE unable to resolve dependency tree
```

**Solution:**
```bash
cd FrontEnd
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
```

### Issue 6: Node.js Not Found
```
'node' is not recognized as an internal or external command
```

**Solution:**
- Install Node.js from https://nodejs.org/
- Recommended: LTS version (16.x or higher)
- After installation, restart terminal

## Advanced Configuration

### Changing LLM Model

Edit `llm_config.json`:
```json
{
  "model": "gpt-4o-mini"  // or other supported models
}
```

Supported models:
- `gpt-5-mini` (default, faster, cheaper)
- `gpt-4o-mini` (more accurate)
- `gpt-4` (most accurate, slower, more expensive)

### Adjusting Parallel Processing

In Python files (e.g., `tag_rate.py`, `job_agent.py`):
```python
MAX_WORKERS = 5  # Reduce for lower API rate limits
```

### Configuring Timeout

In `llm_config.json`:
```json
{
  "timeout": 180  // Increase for slower API responses
}
```

## Production Deployment

For production deployment:

1. **Set environment variables**:
```bash
export FLASK_ENV=production
export OPENAI_API_KEY=your-api-key
```

2. **Use production server** (e.g., Gunicorn):
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 api_server:app
```

3. **Build frontend**:
```bash
cd FrontEnd
npm run build
```

4. **Serve frontend** with nginx or Apache

## Data Files

- **bytedance_jobs.json**: Sample job postings (5.4 MB)
- **tech_taxonomy.json**: Job family hierarchy cache (28 KB)

**Note:** `all_labels.csv` (skill taxonomy) is not included in this submission due to privacy concerns. Users need to provide their own skill taxonomy file with the following format:
- `level_3rd`: Job role category
- `skill_type`: Type of skill
- `tags`: Skill tags (pipe-separated)

Replace these with your own data as needed.

## Support

For additional help:
1. Check inline code documentation
2. Review README.md for component details
3. Check error logs in `backend.log`

---

**Setup completed successfully!** 🎉

You can now use the application by accessing `http://localhost:5173` in your browser.

