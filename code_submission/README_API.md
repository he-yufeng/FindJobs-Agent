# 后端API服务器使用说明

## 功能概述

本项目提供了一个完整的后端服务，支持：

1. **简历解析**：上传PDF简历，自动提取信息并进行技能评分
2. **岗位匹配**：根据简历技能自动匹配最适合的岗位
3. **智能面试（3阶段）**：开场白（Greeting）→ 5轮问答（Q&A，自动评分）→ 总结（Summary）

## 安装依赖

```bash
pip install -r requirements.txt
```

## 启动服务器

```bash
python api_server.py
```

服务器将在 `http://localhost:5000` 启动。

## API接口说明

### 1. 健康检查
- **GET** `/api/health`
- 返回服务器状态

### 2. 简历上传
- **POST** `/api/resume/upload`
- 请求：`multipart/form-data`，字段名：`file`（PDF文件）
- 返回：简历信息和技能评分

### 3. 获取简历
- **GET** `/api/resume/<resume_id>`
- 返回：简历详情

### 4. 获取岗位列表
- **GET** `/api/bdobe_jobs` → 已更新为 `/api/jobs`
- 返回：所有岗位列表（从 `bytedance_jobs_enriched.csv` 加载）

> 注：如果未预生成可用岗位数据，可先在项目根目录运行：`python job_agent.py`，生成/更新 `bytedance_jobs_enriched.csv`。

### 5. 岗位匹配
- **POST** `/api/jobs/match`
- 请求体：
  ```json
  {"resume_id": "<resume_id>"}
  ```
- 返回：匹配结果列表（`matches`），已按“匹配标签数量优先，其次匹配分数”排序。

### 6. 开场白（阶段1：Greeting）
- **POST** `/api/interview/start`
- 请求体（可选）：
  ```json
  { "resume_id": "optional-resume-id", "job_id": "optional-job-id" }
  ```
- 返回（仅开场白＋自我介绍提示，不出题）：
  ```json
  {
    "session_id": "SESSION_UUID",
    "message": "<开场白+自我介绍引导>",
    "question": null,
    "stage": "greeting"
  }
  ```

> 服务端同时初始化会话状态：`phase=greeting, qa_count=0, max_qa=5`。

### 7. 发送面试消息（阶段2&3：Q&A / Summary）
- **POST** `/api/interview/<session_id>/message`
- 请求体：
  ```json
  { "message": "用户的回答或输入" }
  ```
- 返回（结构化回复，按阶段不同）：
  - 处于 `greeting` 阶段：返回过渡话术并给出“第1题”，同时会话进入 `phase=qa`
    ```json
    {
      "message": "<过渡话术>\n\n第1题：\n<问题文本>",
      "stage": "qa",
      "question": "<问题文本>",
      "evaluation": null,
      "qa_count": 0
    }
    ```
  - 处于 `qa` 阶段：对上一题评分并给出下一题
    ```json
    {
      "message": "【评分：4/5】…\n优点：…\n改进建议：…\n\n第<N>题：\n<问题文本>",
      "stage": "qa",
      "question": "<问题文本>",
      "evaluation": {
        "score": 4,
        "feedback": "详细反馈",
        "strengths": ["…"],
        "improvements": ["…"]
      },
      "qa_count": 3
    }
    ```
  - 当 `qa_count` 达到上限（默认5）时：进入 `summary` 阶段，返回总结
    ```json
    {
      "message": "面试结束。以下是您的综合反馈报告：\n<总结文本>",
      "stage": "summary",
      "question": null,
      "evaluation": { "score": 4, "feedback": "…", "strengths": ["…"], "improvements": ["…"] },
      "final_feedback": "<完整总结>",
      "average_score": 4.0
    }
    ```

### 8. 获取面试会话
- **GET** `/api/interview/<session_id>`
- 返回：会话元数据与消息列表

## 前端接入说明

前端代码位于 `FrontEnd/` 目录。

### 启动前端开发服务器
```bash
cd FrontEnd
npm install
npm run dev
```
- 默认地址：`http://localhost:5173`
- 可通过 `FrontEnd/.psn`（或 `.env`）设置：
  ```
  VITE_API_URL=http://localhost:5000/api
  ```
  不设置时将使用内置代理将 `/api` 代理到 `http://localhost:5000`。

## 数据文件要求

确保以下文件存在：

1. `API_key-openai.md` - OpenAI API密钥文件（多行、每行一个key或带别名）
2. `all_labels.csv` - 技能标签库（包含 `level_3rd`、`tags` 等）- **需要用户自行提供（隐私原因未包含在提交包中）**
3. `bytedance_jobs_enriched.csv` - 岗位数据（可通过运行 `python job_agent.py` 生成）
4. （可选）`tech_taxonomy.json` - 岗位族谱缓存（`job_agent.py` 首次运行后生成）

## 注意事项

1. 确保 `tag_rate.py` 在同一目录下（用于加载评分规则与API Key管理）
2. PDF解析使用 `PyPDF2`
3. 所有与LLM相关的API调用依赖 `API_key-openai.md` 中的有效OpenAI密钥
4. 上传的PDF文件大小限制为 10MB
5. 上传的简历文件会保存在 `uploads/`

## 故障排除

### 导入错误
- 确认 `pip install -r requirements.txt` 已执行
- 确认 `tag_rate.py`、`API_key-openai.md` 文件存在
- 确认 `all_labels.csv` 文件存在（需要用户自行提供）

### API调用失败
- 核查 `API_key-openai.md` 格式与密钥是否有效
- 核查代理/防火墙设置，保证能访问 `api.openai.com`

### PDF解析失败
- 确认PDF未加密且内容可复制
- 如日志提示超时，可适当增大 `REQUEST_TIMEOUT`

