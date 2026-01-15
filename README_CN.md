# NLP 项目 - 技术文档

本仓库包含四个由大语言模型（LLM）驱动的智能系统，用于专业技能分析、面试自动化和岗位结构化。

---

## 📋 目录

1. [add_tags.py - 技能标签增强系统](#1-add_tagspy---技能标签增强系统)
2. [AI_interviewer.py - 自适应AI面试系统](#2-ai_interviewerpy---自适应ai面试系统)
3. [tag_rate.py - 简历技能打标与评分系统](#3-tag_ratepy---简历技能打标与评分系统)
4. [job_agent.py - 岗位结构化与分析系统](#4-job_agentpy---岗位结构化与分析系统)

---

## 1. add_tags.py - 技能标签增强系统

### 🎯 功能概述
智能分析现有技能标签列表和真实岗位描述，识别并推荐当前分类体系中缺失的重要技能标签。

### 🏗️ 技术架构

#### 核心组件

**1. API Key 管理器**
- 实现轮询式 API key 轮换
- 支持多个 OpenAI API key 负载均衡
- 线程安全的 key 轮询机制

**2. 数据处理流水线**
```
加载数据 → 聚合描述 → 按类别分组 → LLM分析 → 输出结果
```

**3. LLM 交互模块**
- 模型：`gpt-5-mini`
- Temperature：默认（取决于模型）
- 超时时间：90秒
- 最大重试次数：3次，使用指数退避

**4. 提示工程**
```python
系统角色：顶级行业技能分析专家
核心任务：识别缺失但至关重要的技能
约束条件：
  - 不与现有标签重复
  - 严格相关于技能类型
  - 命名风格与现有标签一致
  - 最多3个新标签，不超过现有数量的一半
输出格式：严格JSON，包含"add"键
```

### 📦 依赖项
```python
- pandas: 数据处理
- requests: API通信
- json: 响应解析
- concurrent.futures: 并行处理
```

### ⚙️ 配置说明

**文件路径：**
```python
TAGS_CSV = "all_labels copy.csv"          # 输入：现有标签
USER_DATA_CSV = "merged_user_descriptions.csv"  # 输入：岗位描述
OUTPUT_CSV = "new_labels_list.csv"        # 输出：增强后的标签
API_KEY_FILE = "API_key-openai.md"               # API密钥文件
```

**API 设置：**
```python
API_URL = "https://api.openai.com/v1/chat/completions"
MODEL_NAME = "gpt-5-mini"
TIMEOUT = 90
MAX_RETRY = 3
MAX_WORKERS = min(len(API_KEYS), 10)
```

### 📊 输入格式

**all_labels copy.csv:**
```csv
level_3rd,skill_type,tags
软件工程师,技术技能,Python|_|Java|_|Docker
产品经理,产品设计,用户研究|_|原型设计
```

**merged_user_descriptions.csv:**
```csv
exp_type,work_lv3_name,work_description
WORK,软件工程师,使用Go和Kubernetes开发微服务...
WORK,产品经理,通过50+用户访谈主导产品发现...
```

### 🚀 使用方法

**基本执行：**
```bash
python add_tags.py
```

**API密钥配置 (API_key-openai.md):**
```
# OpenAI API Keys
user1 sk-proj-xxxxxxxxxxxxx
user2 sk-proj-yyyyyyyyyyyyy
user3 "sk-proj-zzzzzzzzzzzzz"
```

### 📤 输出格式

**new_labels_list.csv:**
```csv
level_3rd,skill_type,original_cnt,add_cnt,original_tags,suggested_add_tags
软件工程师,技术技能,5,2,Python|_|Java|_|Docker|_|...,Kubernetes|_|Go
产品经理,产品设计,8,1,用户研究|_|原型设计|_|...,A/B测试
```

### 🔧 关键特性

1. **智能聚合**：按角色类别合并岗位描述，限制4000字符
2. **并行处理**：多线程执行，可配置工作线程数
3. **上下文感知分析**：LLM考虑真实岗位案例
4. **严格验证**：JSON解析带回退机制
5. **编码健壮性**：支持多种编码（utf-8, gbk, gb2312等）

### ⚠️ 注意事项

- **速率限制**：API错误时自动指数退避
- **Token限制**：每个角色的岗位描述截断至4000字符
- **输出验证**：仅接受有效的JSON响应
- **重复防止**：系统确保不与现有标签重复

---

## 2. AI_interviewer.py - 自适应AI面试系统

### 🎯 功能概述
智能面试系统，能够动态生成问题、评估答案、提供反馈，并根据候选人表现自适应调整难度。

### 🏗️ 技术架构

#### 核心组件

**1. LLMClient**
```python
- 模型支持：gpt-5-mini、gpt-4o-mini（受温度限制）及其他
- Temperature：0.7（生成任务）、0.2（结构化任务）
- 自动检测：处理不支持温度的模型
- 响应模式：文本生成、JSON生成
```

**2. InterviewModule**
```python
generate_questions():
  - 基于表现历史的自适应难度
  - 每场3-5道主观题
  - 包含参考答案、思考指引、评分细则

grade_answer():
  - 0-5分量表
  - 多维度评分（理解力、逻辑、可行性、深度、表达）
  - 自动追问检测

generate_followup():
  - 上下文感知的澄清问题
  - 友好引导的语气
  - 最多30字符
```

**3. InterviewOrchestrator**
```python
工作流程：
  1. 用户输入：领域、技能类型、核心技能
  2. 生成开场白
  3. 初始问题批次（3题）
  4. 基于表现的自适应问题生成
  5. 评分，可选追问
  6. 最终综合报告
```

### 📦 依赖项
```python
- openai: OpenAI官方Python客户端
- json: 结构化数据处理
- logging: 全面日志记录
- dataclasses: 类型安全的数据结构
```

### ⚙️ 配置说明

**模型设置：**
```python
MODEL = 'gpt-5-mini'
TIMEOUT_S = 180
MAX_RETRY = 3
TEMPERATURE = 0.7
```

**难度自适应：**
```python
if avg_score >= 4.0:
    → 生成更难的问题（最多5题）
elif avg_score <= 2.0:
    → 生成更简单的问题（最少2题）
else:
    → 保持标准难度
```

### 🚀 使用方法

**基本执行：**
```bash
python AI_interviewer.py
```

**交互流程：**
```
1. 输入职业领域（如："软件工程师"）
2. 输入技能类型（如："软件开发"）
3. 输入核心技能（如："大模型Agent开发"）
4. 回答问题（多行输入，以'END'结束）
5. 接收评分和反馈
6. 回答可选追问
7. 获得最终综合报告
```

### 📊 问题结构

**JSON Schema:**
```json
{
  "questions": [
    {
      "question_type": "subjective",
      "question": "设计一个文档问答Agent...",
      "difficulty": "medium",
      "reference_answer": "应包含检索、LLM推理...",
      "thinking_guide": "考虑可扩展性和错误处理...",
      "grading_rubric": "0分：未回答\n1分：误解需求\n..."
    }
  ]
}
```

### 📈 评分维度

1. **问题理解** (0-5)：准确识别需求
2. **逻辑结构** (0-5)：连贯性和组织性
3. **方案可行性** (0-5)：实用性和工程约束
4. **细节深度** (0-5)：具体性和实现细节
5. **沟通表达** (0-5)：清晰度和专业性

### 📤 最终报告结构

```
==================================================
面试结束 - 综合反馈报告
==================================================
最终平均得分: 3.80 / 5.00
表现趋势: 表现稳定

总体评价（约120字）
[综合评估...]

亮点分析
- [亮点1，含具体示例]
- [亮点2，含具体示例]

改进建议（优先级顺序，含可执行步骤）
1) [高优先级改进，含行动步骤]
2) [次优先级改进，含行动步骤]

能力画像（简要）
[候选人能力总结]

学习建议（可操作）
1) [具体学习建议]
2) [练习建议]

总评语
[鼓励性结束语]
==================================================
```

### 🔧 关键特性

1. **自适应难度**：问题根据滚动平均分调整
2. **智能追问**：系统检测何时需要澄清
3. **详尽评分细则**：每题都有详细的0-5分锚点
4. **多行输入**：支持复杂、格式化的答案
5. **趋势分析**：跟踪表现轨迹（改善/下降/稳定）
6. **可操作反馈**：具体、可执行的改进建议

### ⚠️ 注意事项

- **API Key轮换**：自动循环使用多个key
- **温度兼容性**：自动检测模型温度支持
- **会话状态**：保持面试历史记录作为上下文
- **重试逻辑**：失败时使用带抖动的指数退避
- **输入验证**：优雅处理空/无效响应

---

## 3. tag_rate.py - 简历技能打标与评分系统

### 🎯 功能概述
使用LLM分析用户简历，从官方分类体系中分配技能标签，评定熟练度（1-5分），并补充缺失技能——全部基于严格的评分标准。

### 🏗️ 技术架构

#### 核心组件

**1. APIKeyManager**
```python
- 线程安全的key轮换
- 自动负载均衡
- 支持10+并发API key
```

**2. 数据处理流水线**
```
加载数据 → 计算用户关系 → 按网络规模排序 → 
处理Top N用户 → 评分标签 → 补充缺失标签 → 保存结果
```

**3. 评分框架（V4版本）**

**基于锚点的评估：**
```
基准分：3分（熟练）
  ↓
降分规则（强制）：
  - 2分：仅辅助/参与性任务，缺乏独立证据
  - 1分：仅提及，无项目证据

加分规则（严格，可选）：
  - 4分：高级领导力、可量化影响、顶级公司高级职位
  - 5分：行业专家、高管职位、重大开源/学术贡献
```

**背景因素检查表：**
```python
教育背景：
  - 博士 > 硕士 > 本科
  - 全球Top 50/C9 > 985/211 > 普通院校

工作经验：
  - 顶级公司（FAANG、BAT）> 知名 > 中小企业
  - 5年以上达"精通"，10年以上达"专家"
  - 总监/首席 > 经理/高级 > 初级
```

**4. 任务执行**

**任务1：评分现有标签**
```python
输入：无分数的标签（score=0）
处理：LLM基于简历评估
输出：带1-5分的标签，source='AI'
```

**任务2：补充缺失标签**
```python
输入：未达到目标数量
处理：LLM从候选池中选择
输出：新标签带分数，source='AI'
约束：不重复，需要精确匹配
```

### 📦 依赖项
```python
- pandas: DataFrame操作
- requests: HTTP API调用
- argparse: CLI参数解析
- concurrent.futures: 并行处理
```

### ⚙️ 配置说明

**全局设置：**
```python
API_URL = 'https://api.openai.com/v1/chat/completions'
MODEL = 'gpt-5-mini'
TIMEOUT_S = 120
MAX_RETRY = 3
TOP_N = 500  # 处理的Top用户数
MAX_WORKERS = 10  # 并行线程数
```

**文件路径：**
```python
USER_PROFILE_CSV = 'user_descriptions copy.csv'
OFFICIAL_TAGS_CSV = 'all_labels.csv'
API_KEY_FILE = 'API_key-openai.md'
OUTPUT_CSV = 'ai_user_tags.csv'  # 既是输入也是输出
RELATIONSHIP_CSV = 'user_relationship_sorted.csv'
```

### 📊 输入格式

**user_descriptions copy.csv:**
```csv
uid,exp_type,work_lv3_name,work_company,work_position,work_start_date,work_end_date,work_description,edu_school,edu_major
12345,WORK,软件工程师,Google,高级SWE,2020-01,至今,领导ML基础设施团队...,斯坦福大学,计算机科学
12345,EDU,,,,,,,斯坦福大学,计算机科学
```

**all_labels.csv:**
```csv
level_3rd,skill_type,tags
软件工程师,编程语言,Python|_|Java|_|Go|_|C++
数据科学家,机器学习,深度学习|_|NLP|_|计算机视觉
```

**ai_user_tags.csv（已存在，可选）:**
```csv
uid,tags
12345,Python , 0 , HM | Java , 0 , HM | TensorFlow , 3 , AI
67890,产品设计 , 0 , HM
```

### 🚀 使用方法

**基本执行：**
```bash
python tag_rate.py
```

**自定义目标标签数量：**
```bash
python tag_rate.py --num-tags 8
```

**CLI参数：**
```bash
-n, --num-tags    每个用户的目标标签数（默认：5）
```

### 📤 输出格式

**ai_user_tags.csv:**
```csv
uid,tags
12345,Python , 4 , AI | 机器学习 , 4 , AI | Docker , 3 , AI | Kubernetes , 3 , AI | TensorFlow , 4 , AI
67890,产品设计 , 3 , AI | 用户研究 , 3 , AI | 原型设计 , 2 , AI | A/B测试 , 3 , AI | Figma , 3 , AI
```

**标签格式：**
```
<标签名> , <分数1-5> , <来源AI|HM> | <下一个标签> | ...
```

### 🔧 关键特性

1. **社交网络排序**：优先处理连接最多的用户（同事、校友）
2. **增量处理**：保留已评分标签，仅处理需要的部分
3. **双任务系统**：
   - 评分未评分标签
   - 补充缺失标签至目标数量
4. **严格评分**：V4框架，强制降分和严格升分规则
5. **上下文感知候选**：标签匹配用户的工作类别（level_3rd）
6. **并行执行**：10个并发工作线程的多线程
7. **简历构建**：将工作/教育历史聚合成连贯的简历文本

### ⚠️ 注意事项

- **用户关系计算**：
  - 现任同事（同公司，目前在职）
  - 前同事（同公司，任何时期）
  - 校友（同学校）
- **候选池**：标签按用户的work_lv3_name类别筛选
- **LLM输出解析**：严格正则`([^:：\s]+?)\s*[:：]\s*([1-5])`带验证
- **错误处理**：单个用户失败不会停止批处理
- **数据保留**：不在Top N中的用户保留其现有标签
- **编码健壮性**：支持utf-8、gbk、gb2312、gb18030、utf-8-sig、latin1

---

## 4. job_agent.py - 岗位结构化与分析系统

### 🎯 功能概述
高级系统，分析岗位招聘信息，提取结构化信息，包括学历要求、专业要求、带熟练度的技能标签和岗位族分类——同时检测岗位强度信号以校准技能评分。

### 🏗️ 技术架构

#### 核心组件

**1. SkillRepository**
```python
- 加载all_labels.csv技能分类体系
- 岗位文本与level_3rd类别的模糊匹配
- 动态候选选择（前12个类别，每个岗位约80个技能）
- 直接文本匹配 + 后备池（150个常见技能）
```

**2. TaxonomyManager**
```python
- 构建180-220个二级岗位角色，覆盖18-22个一级分类
- 使用user_descriptions.csv获取真实岗位频率
- LLM生成层次结构，带关键词索引
- 持久化缓存到tech_taxonomy.json
```

**3. JobSignalAnalyzer**
```python
强度信号：
  - 博士学位项目
  - 旗舰/人才计划
  - 国际实验室
  - 顶级会议（ACL、NeurIPS、CVPR等）
  - 前沿LLM/Agent研究

强度等级：
  - flagship_research（分数≥9，base=5）
  - research（分数≥6，base=4）
  - advanced（分数≥3，base=3）
  - standard（分数≥0，base=3）
```

**4. KnowledgeRetriever**
```python
- 从岗位文本提取项目/实验室名称
- 通过DuckDuckGo即时API获取背景信息
- 缓存结果到program_context_cache.json
- 为LLM提供额外上下文以改善评分
```

**5. SkillNormalizer**
```python
- 替换泛化技能（AI、技术、数学）为具体替代品
- 根据官方技能分类验证
- 移除低信息量重复项
```

**6. SkillReviewAgent**
```python
- 后处理质量保证
- 对于高强度岗位（base≥4），复核低分
- 使用LLM根据信号向上调整分数（如有依据）
- 确保与岗位要求对齐
```

**7. JobAgent（主编排器）**
```python
每个岗位的工作流程：
  1. 提取岗位文本（标题、描述、要求）
  2. 从SkillRepository获取候选技能
  3. 从TaxonomyManager获取岗位族候选
  4. 分析岗位强度（信号）
  5. 检索项目背景（如适用）
  6. 用综合提示调用LLM
  7. 解析和验证LLM输出
  8. 归一化和选择技能（3-10个）
  9. 基于强度复核技能
  10. 格式化并返回结构化结果
```

### 📦 依赖项
```python
- pandas: 数据操作
- requests: API通信
- argparse: CLI解析
- difflib: 模糊搜索的序列匹配
- concurrent.futures: 并行岗位处理
- tag_rate: 导入APIKeyManager、COMMON_SCORING_RULES_V4、format_tags_for_csv
```

### ⚙️ 配置说明

**API设置：**
```python
API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-5-mini"
REQUEST_TIMEOUT = 120
MAX_LLM_RETRY = 3
MAX_WORKERS = 10
```

**信号检测：**
```python
SIGNAL_RULES = [
  {"label": "博士学位", "weight": 4, "tier": "research"},
  {"label": "旗舰/人才计划", "weight": 3, "tier": "flagship"},
  {"label": "国际/跨国实验室", "weight": 2, "tier": "research"},
  {"label": "顶级会议/科研成果", "weight": 3, "tier": "research"},
  {"label": "前沿大模型/Agent研究", "weight": 2, "tier": "research"}
]
```

**文件路径：**
```python
DEFAULT_JOBS_FILE = "bytedance_jobs copy.json"
DEFAULT_LABELS_FILE = "all_labels.csv"
DEFAULT_USER_DESC_FILE = "user_descriptions.csv"
DEFAULT_TAXONOMY_FILE = "tech_taxonomy.json"
DEFAULT_OUTPUT_FILE = "bytedance_jobs_enriched.csv"
DEFAULT_API_KEY_FILE = "API_key-openai.md"
PROGRAM_CACHE_FILE = "program_context_cache.json"
```

### 📊 输入格式

**bytedance_jobs copy.json:**
```json
[
  {
    "job_id": "JOB001",
    "company_name": "字节跳动",
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

**user_descriptions.csv（用于构建分类体系）:**
```csv
uid,exp_type,work_lv3_name
1,WORK,搜广推算法工程师
2,WORK,Java后端开发
3,WORK,产品经理
```

### 🚀 使用方法

**基本执行：**
```bash
python job_agent.py
```

**完整参数指定：**
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

**强制重建分类体系：**
```bash
python job_agent.py --rebuild-taxonomy
```

**CLI参数：**
```bash
--jobs-file PATH         输入岗位JSON文件
--labels-file PATH       技能分类体系CSV
--user-desc-file PATH    构建分类体系的用户描述
--taxonomy-file PATH     岗位族分类体系JSON（缓存）
--output-file PATH       输出CSV文件
--api-key-file PATH      API密钥文件
--model STR              LLM模型名称（默认：gpt-5-mini）
--min-skills INT         每个岗位最少技能数（默认：3）
--max-skills INT         每个岗位最多技能数（默认：10）
--max-workers INT        并行线程数（默认：10）
--rebuild-taxonomy       强制重建岗位分类体系
--verbose                启用调试日志
```

### 📤 输出格式

**bytedance_jobs_enriched.csv:**
```csv
job_id,company_name,job_title,category,location,special_program,job_description,job_requirements,apply_url,min_degree,degree_priority,major_requirement_text,major_requirement_priority,skill_tags,job_level1,job_level2,llm_raw_json
JOB001,字节跳动,大模型Agent研究员,算法,北京,Top Seed Program,[原始文本],[原始文本],https://...,博士,必须,计算机科学、人工智能、NLP相关专业,必须,深度学习 , 5 , AI | 强化学习 , 4 , AI | NLP , 5 , AI | PyTorch , 4 , AI | LangChain , 3 , AI,算法,大模型研究,{...}
```

**技能标签格式：**
```
<技能> , <分数1-5> , AI | <下一个技能> , <分数> , AI | ...
```

### 🔧 关键特性

1. **智能技能匹配**：
   - 岗位文本与技能类别的模糊匹配
   - 岗位描述内的直接文本搜索
   - 边缘情况的全局后备池

2. **动态岗位分类体系**：
   - 从真实岗位数据自动生成180-220个二级角色
   - 基于关键词匹配，带置信度评分
   - 一次性LLM构建，持久化缓存

3. **岗位强度检测**：
   - 5种信号类型，带权重评分
   - 自动基准分调整（3→4→5）
   - 信号感知的技能评分

4. **外部知识检索**：
   - 识别项目/实验室名称
   - 从DuckDuckGo获取背景信息
   - 用背景信息丰富LLM提示

5. **质量保证**：
   - SkillNormalizer移除泛化术语
   - SkillReviewAgent验证高强度岗位
   - 确保每个岗位3-10个技能，带后备

6. **并行处理**：
   - 多线程岗位处理
   - 线程安全的API key轮换
   - 进度跟踪和错误隔离

### 📋 LLM提示结构

```
### 系统提示
- 角色：资深人力与技能分析专家
- 评分框架：COMMON_SCORING_RULES_V4（来自tag_rate.py）
- 输出：严格JSON格式

### 用户提示组件
1. 岗位信息
   - 公司、标题、类别、地点、项目
   - 描述和要求

2. 强度评估
   - 强度等级和基准分
   - 检测到的信号及解释

3. 外部知识
   - 项目/实验室背景摘要

4. 候选技能
   - 来自SkillRepository的3-10个技能
   - 必须精确从此列表选择

5. 岗位族候选
   - 前4个一级分类，带二级选项
   - 最多40个二级角色

6. 输出Schema
   {
     "min_degree": {"degree": "本科|硕士|博士|大专", "priority": "必须|优先"},
     "major_requirement": {"text": "...", "priority": "必须|优先"},
     "skills": [{"name": "技能名", "score": 1-5}, ...],
     "job_family": {"level1": "...", "level2": "..."}
   }
```

### ⚠️ 注意事项

- **分类体系构建**：首次运行可能需要30-60秒构建岗位分类体系
- **项目背景**：需要互联网访问以进行DuckDuckGo查询
- **技能验证**：所有技能必须存在于all_labels.csv中
- **评分对齐**：使用与tag_rate.py相同的V4框架
- **错误处理**：单个岗位失败不会停止批处理
- **缓存管理**：
  - tech_taxonomy.json：岗位族层次结构
  - program_context_cache.json：外部知识
- **性能**：含API调用，每个岗位约10-15秒

---

## 🔑 通用设置

### API密钥配置

在项目根目录创建`API_key-openai.md`：

```markdown
# OpenAI API Keys

alice sk-proj-abc123...
bob "sk-proj-def456..."
charlie sk-proj-ghi789...
```

### 文件结构
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
├── ai_user_tags.csv（生成）
├── new_labels_list.csv（生成）
├── bytedance_jobs_enriched.csv（生成）
├── user_relationship_sorted.csv（生成）
├── tech_taxonomy.json（生成）
└── program_context_cache.json（生成）
```

### Python环境
```bash
pip install pandas requests openai
```

---

**最后更新：** 2025-11-15

