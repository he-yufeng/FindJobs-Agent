# 后端 API 服务器使用说明

## 功能概述

后端服务 `findjobs.api_server`（Flask）提供：

1. **简历解析**：上传 PDF 简历，自动提取信息并进行技能评分
2. **岗位匹配**：根据简历技能自动匹配最适合的岗位
3. **智能面试（3 阶段）**：开场白（Greeting）→ 5 轮问答（Q&A，自动评分）→ 总结（Summary）
4. **投递看板**：跟踪每个岗位的投递状态

## 安装与启动

```bash
pip install -e .
python -m findjobs.api_server
```

服务器默认在 `http://localhost:5000` 启动（`PORT` 环境变量可改）。

## API 接口一览

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| POST | `/api/resume/upload` | 上传 PDF 简历（`multipart/form-data`，字段 `file`），返回解析结果与技能评分 |
| GET | `/api/resume/<resume_id>` | 简历详情 |
| GET | `/api/resume/file/<file_id>` | 取回原 PDF 文件 |
| GET | `/api/jobs` | 岗位列表（来自 `jobs.db`，空库在 Demo 模式下自动播种示例岗位） |
| POST | `/api/jobs/match` | 岗位匹配，请求体 `{"resume_id": "..."}`，返回按匹配度排序的 `matches` |
| POST | `/api/interview/start` | 开场白，可选 `{"resume_id": "...", "job_id": "..."}`，返回 `session_id` |
| POST | `/api/interview/<session_id>/message` | 发送回答，按阶段返回评分与下一题 |
| GET | `/api/interview` | 全部面试会话索引（按开始时间倒序，不含消息正文） |
| GET | `/api/interview/<session_id>` | 单个会话的元数据与消息列表 |
| GET | `/api/applications` | 投递看板：每个被跟踪岗位的当前状态 |
| PUT | `/api/applications/<job_id>` | 标记或更新投递状态，请求体 `{"status": "...", "note": "..."}` |
| DELETE | `/api/applications/<job_id>` | 从看板移除一个岗位 |

## 面试阶段协议

### 开场白（阶段 1：Greeting）

`POST /api/interview/start` 返回：

```json
{
  "session_id": "SESSION_UUID",
  "message": "<开场白+自我介绍引导>",
  "question": null,
  "stage": "greeting"
}
```

服务端同时初始化会话状态：`phase=greeting, qa_count=0, max_qa=5`。

### 问答与总结（阶段 2&3：Q&A / Summary）

`POST /api/interview/<session_id>/message`，请求体 `{ "message": "用户的回答" }`，按阶段返回：

- `greeting` 阶段：返回过渡话术并给出第 1 题，会话进入 `phase=qa`
- `qa` 阶段：对上一题评分并给出下一题，`evaluation` 带 `score` / `feedback` / `strengths` / `improvements`
- `qa_count` 达到上限（默认 5）后进入 `summary`，返回 `final_feedback` 与 `average_score`

## 前端接入

前端代码在 `FrontEnd/`：

```bash
cd FrontEnd
npm install
npm run dev
```

- 默认地址 `http://localhost:5173`
- 开发服务器已把 `/api` 代理到 `http://localhost:5000`（见 `FrontEnd/vite.config.ts`）；要指向别的后端，设 `VITE_API_URL` 环境变量。

## 部署说明

ModelScope / Docker 部署参考 `config/ms_deploy.example.json`，根目录的 `Dockerfile` 可直接构建后端镜像（默认端口 7860）。真实的 `ms_deploy.json` 属于本地部署文件，已在 `.gitignore` 中忽略；请把 `OPENROUTER_API_KEY` 放在平台密钥或环境变量里，不要提交真实 key。

## 数据与配置

1. 岗位与面试数据都在根目录 `jobs.db`（SQLite），首次运行自动建表；Demo 模式（`FINDJOBS_DEMO=1`）下空库自动从 `data/sample_jobs.json` 播种。
2. 技能标签库在 `data/all_labels.csv`，岗位族谱缓存在 `data/tech_taxonomy.json`。
3. LLM key 从环境变量（`OPENROUTER_API_KEY` / `OPENAI_API_KEY`）读取，也可放根目录 `API_key-openai.md`（多行、每行一个 key 或带别名），该文件已在 `.gitignore` 中忽略。

## 注意事项

1. PDF 解析使用 `pypdf`。
2. 上传的 PDF 限制 10MB，文件保存在 `uploads/`。
3. Demo 模式下所有 LLM 调用走离线桩 `findjobs/demo_llm.py`，不消耗任何 key。

## 故障排除

### 导入错误
- 确认已执行 `pip install -e .`

### API 调用失败
- 核查 key 是否有效（环境变量或 `API_key-openai.md`）
- 核查代理/防火墙设置，保证能访问对应的 LLM 端点

### PDF 解析失败
- 确认 PDF 未加密且内容可复制
