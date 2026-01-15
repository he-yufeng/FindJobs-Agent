#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import time
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional, NamedTuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import pandas as pd
import requests

# --- 日志配置 (Logging Configuration) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 全局配置 (Global Configuration) ---
API_URL = 'https://api.openai.com/v1/chat/completions'
MODEL = 'gpt-5-mini'  # OpenAI 官方模型名称
TIMEOUT_S = 120  # 增加超时时间以应对更复杂的Prompt和网络波动
MAX_RETRY = 3  # API请求失败后的最大重试次数
TOP_N = 500  # 选取排序后的前N位用户进行实验
MAX_WORKERS = 10  # 并行处理的最大线程数（对应10个API keys）

# --- 文件路径配置 (File Path Configuration) ---
ROOT_DIR = Path(__file__).resolve().parent
USER_PROFILE_CSV = ROOT_DIR / 'user_descriptions copy.csv'
OFFICIAL_TAGS_CSV = ROOT_DIR / 'all_labels.csv'
API_KEY_FILE = ROOT_DIR / 'API_key-openai.md'
# 注意：OUTPUT_CSV 现在既是输入也是输出
OUTPUT_CSV = ROOT_DIR / 'ai_user_tags.csv'
RELATIONSHIP_CSV = ROOT_DIR / 'user_relationship_sorted.csv'

# --- 定义标签数据结构 (Define Tag Data Structure) ---
class Tag(NamedTuple):
    """用于清晰地表示一个标签及其属性"""
    name: str
    score: int
    source: str  # 'AI' 或 'HM' (Human)

# --- API Key 管理器 (API Key Manager) ---
class APIKeyManager:
    """管理多个 API keys，实现轮询使用"""
    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.lock = Lock()
        self.current_index = 0
        if not self.api_keys:
            raise ValueError("至少需要提供一个 API key")
        logging.info(f"初始化 API Key 管理器，共 {len(self.api_keys)} 个 keys")
    
    def get_key(self) -> str:
        """获取下一个可用的 API key（轮询）"""
        with self.lock:
            key = self.api_keys[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.api_keys)
            return key

def load_api_keys(file_path: Path) -> List[str]:
    """从 API_key-openai.md 文件加载所有 API keys"""
    api_keys = []
    if not file_path.exists():
        raise FileNotFoundError(f"API key 文件不存在: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # 格式: heyufengX sk-proj-xxx 或直接是 sk-proj-xxx
                parts = line.split()
                for part in parts:
                    if part.startswith('sk-proj-') or part.startswith('sk-'):
                        api_keys.append(part)
                        break
                else:
                    # 如果没有找到 sk- 开头的，可能是直接就是 key
                    if 'sk-' in line:
                        # 尝试提取 sk- 之后的内容
                        idx = line.find('sk-')
                        if idx != -1:
                            potential_key = line[idx:].strip()
                            if potential_key.startswith('sk-proj-') or potential_key.startswith('sk-'):
                                api_keys.append(potential_key)
        
        if not api_keys:
            raise ValueError(f"在 {file_path} 中未找到任何有效的 API key")
        
        # 去重但保持顺序
        seen = set()
        unique_keys = []
        for key in api_keys:
            if key not in seen:
                seen.add(key)
                unique_keys.append(key)
        
        logging.info(f"成功加载 {len(unique_keys)} 个 API keys")
        return unique_keys
    except Exception as e:
        logging.error(f"加载 API keys 失败: {e}")
        raise

# --- 模块 1: 数据加载与预处理 (Data Loading & Preprocessing) ---

def load_and_preprocess_data() -> Tuple[pd.DataFrame, Dict[str, Set[str]], Dict[int, str]]:
    """
    加载所有必需的CSV文件，进行严格的清洗和预处理。
    现在还会加载并返回已存在的输出文件内容。
    """
    logging.info("模块 1: 开始加载和预处理数据...")
    try:
        user_df = pd.read_csv(USER_PROFILE_CSV)
        tags_df = pd.read_csv(OFFICIAL_TAGS_CSV)
        logging.info(f"成功加载文件: {USER_PROFILE_CSV.name}, {OFFICIAL_TAGS_CSV.name}")

        required_cols = {
            'user': {'uid', 'exp_type', 'work_lv3_name', 'work_company', 'work_end_date', 'edu_school'},
            'tags': {'level_3rd', 'tags'},
        }
        for df_name, df, cols in [('user', user_df, required_cols['user']), ('tags', tags_df, required_cols['tags'])]:
            if not cols.issubset(df.columns):
                raise ValueError(f"文件 '{df_name}.csv' 必须包含 {cols} 列。")

        logging.info("正在清洗和统一用户简历表的数据类型...")
        original_rows = len(user_df)
        user_df.dropna(subset=['uid'], inplace=True)
        user_df['uid'] = pd.to_numeric(user_df['uid'], errors='coerce')
        user_df.dropna(subset=['uid'], inplace=True)
        user_df['uid'] = user_df['uid'].astype(int)
        cleaned_rows = len(user_df)
        if original_rows > cleaned_rows:
            logging.warning(f"在'用户简历表'中，移除了 {original_rows - cleaned_rows} 行无效或空的uid。")

        official_tags_dict: Dict[str, Set[str]] = {}
        tags_df.dropna(subset=['level_3rd', 'tags'], inplace=True)
        for _, row in tags_df.iterrows():
            lv3 = str(row['level_3rd']).strip()
            tags = {t.strip() for t in str(row['tags']).split('|_|') if t.strip()}
            if lv3:
                official_tags_dict.setdefault(lv3, set()).update(tags)

        existing_tags_data: Dict[int, str] = {}
        if OUTPUT_CSV.exists():
            logging.info(f"发现已存在的输出文件，正在加载: {OUTPUT_CSV.name}")
            try:
                existing_df = pd.read_csv(OUTPUT_CSV)
                if 'uid' in existing_df.columns and 'tags' in existing_df.columns:
                    existing_df.dropna(subset=['uid'], inplace=True)
                    existing_df['uid'] = pd.to_numeric(existing_df['uid'], errors='coerce').astype('Int64')
                    existing_df.dropna(subset=['uid'], inplace=True)
                    existing_tags_data = pd.Series(
                        existing_df.tags.values,
                        index=existing_df.uid
                    ).to_dict()
                    logging.info(f"成功加载了 {len(existing_tags_data)} 位用户的现有标签。")
                else:
                    logging.warning(f"文件 '{OUTPUT_CSV.name}' 格式不正确，缺少 'uid' 或 'tags' 列，将作为空文件处理。")
            except Exception as e:
                logging.error(f"加载现有输出文件 '{OUTPUT_CSV.name}' 失败: {e}，将作为空文件处理。")
        else:
            logging.info(f"未找到现有的输出文件 '{OUTPUT_CSV.name}'，将创建新文件。")

        logging.info("数据加载和预处理完毕。")
        return user_df, official_tags_dict, existing_tags_data

    except FileNotFoundError as e:
        logging.critical(f"文件未找到: {e}。请确保所有CSV文件与脚本位于同一目录。", exc_info=True)
        exit(1)
    except ValueError as e:
        logging.critical(f"数据文件列不匹配或数据问题: {e}。", exc_info=True)
        exit(1)
    except Exception as e:
        logging.critical(f"加载数据时发生未知错误: {e}", exc_info=True)
        exit(1)

# --- 模块 2: 用户关系计算与排序 (User Relationship Calculation & Sorting) ---
# (此模块与原版相同，保持不变)
def calculate_relationships_and_sort(user_df: pd.DataFrame, top_n: int) -> List[int]:
    logging.info("模块 2: 开始计算用户关系并排序...")
    df = user_df.copy()
    
    for col in ['work_company', 'edu_school', 'work_end_date', 'work_description']:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str).str.strip()

    company_to_uids: Dict[str, Set[int]] = {}
    current_company_to_uids: Dict[str, Set[int]] = {}
    school_to_uids: Dict[str, Set[int]] = {}
    
    work_df = df[df['exp_type'] == 'WORK'].copy()
    work_df.loc[:, 'is_current'] = work_df['work_end_date'].str.contains('至今|Present', case=False, na=False) | (work_df['work_end_date'] == '')

    for company, group in work_df.groupby('work_company'):
        if not company: continue
        all_uids = set(group['uid'])
        company_to_uids[company] = all_uids
        current_uids = set(group[group['is_current']]['uid'])
        if current_uids:
            current_company_to_uids[company] = current_uids

    edu_df = df[df['exp_type'] == 'EDU']
    for school, group in edu_df.groupby('edu_school'):
        if not school: continue
        school_to_uids[school] = set(group['uid'])

    logging.info("倒排索引构建完成。")
    
    relationship_counts = []
    all_uids = df['uid'].unique()
    for uid in all_uids:
        user_work = work_df[work_df['uid'] == uid]
        user_edu = edu_df[edu_df['uid'] == uid]
        
        user_companies = set(user_work['work_company']) - {''}
        user_current_companies = set(user_work[user_work['is_current']]['work_company']) - {''}
        user_schools = set(user_edu['edu_school']) - {''}

        current_colleagues = {u for c in user_current_companies for u in current_company_to_uids.get(c, set())}
        all_colleagues = {u for c in user_companies for u in company_to_uids.get(c, set())}
        alumni = {u for s in user_schools for u in school_to_uids.get(s, set())}

        relationship_counts.append({
            'uid': uid,
            'current_colleagues': len(current_colleagues - {uid}),
            'former_colleagues': len(all_colleagues - {uid}),
            'alumni': len(alumni - {uid})
        })

    if not relationship_counts:
        logging.warning("未能计算任何用户关系，返回空列表。")
        return []

    rel_df = pd.DataFrame(relationship_counts)
    sorted_df = rel_df.sort_values(by=['current_colleagues', 'former_colleagues', 'alumni'], ascending=[False, False, False])
    
    try:
        sorted_df.to_csv(RELATIONSHIP_CSV, index=False, encoding='utf-8-sig')
        logging.info(f"用户关系排序已完成，并保存中间文件到 '{RELATIONSHIP_CSV.name}'。")
    except Exception as e:
        logging.warning(f"保存中间排序文件失败: {e}", exc_info=True)

    top_uids = sorted_df.head(top_n)['uid'].tolist()
    logging.info(f"成功选取 Top {len(top_uids)} 位用户进行后续处理。")
    return top_uids

# --- 模块 3: 大语言模型交互 (LLM Interaction) ---

# 针对不同任务的System Prompt (V4 - 最终版)
COMMON_SCORING_RULES_V4 = (
    "## 评分框架 (1-5分整数)\n\n"
    "你的评分过程必须遵循“基准分评估”和“动态调整”两个步骤。\n\n"
    "**第一步：设定基准分 (Anchor Score)**\n"
    "所有技能的初始评估都从 **3分 (熟练)** 这个锚点开始。首先判断用户的经验描述是否达到了“熟练”的标准。\n"
    "- **3分 (熟练/Proficient)**: 这是核心基准。代表用户能**独立负责**常规项目或模块，是团队的可靠贡献者。简历中必须有**至少1-2个**能支撑这一点的具体项目描述。\n\n"
    "**第二步：动态调整 (Dynamic Adjustment)**\n"
    "在基准分基础上，根据以下规则进行加减分，得出最终分数。\n\n"
    "### 降分规则 (MANDATORY)\n"
    "- **降至 2分 (入门/Beginner)**: 如果技能仅在**辅助性、参与性**任务中体现，或项目描述**过于简单、缺乏细节**，无法证明其独立性，则从3分降至2分。对于缺乏具体项目细节、仅在职责中笼统提及的技能，**必须优先考虑2分**。\n"
    "- **降至 1分 (认知/Learner)**: 如果技能**仅在简历中被提及**，或仅在课程/证书中出现，**无任何实际项目经验作为证据**，则从3分降至1分。对于仅在简历中列出，无任何对应描述的技能，**必须给予1分**。\n\n"
    "### 加分规则 (OPTIONAL & STRICT)\n"
    "- **升至 4分 (精通/Advanced)**: 必须有**强力、明确的证据**才能从3分升至4分。满足以下**至少一项**: \n"
    "    - **项目影响力**: 主导过**高复杂度、大规模或从0到1**的关键项目，并有可量化的成果（如：提升XX%效率，带来XX万收入）。\n"
    "    - **职位与公司**: 在**顶级大厂/知名企业**担任**高级/资深/专家/Lead**职位，且有**指导/培养**团队成员的明确描述。\n"
    "    - **技术深度**: 解决了公认的**技术难题**，或对公司核心架构有**重大贡献**（如：重构系统、引入新技术栈并成功落地）。\n"
    "- **升至 5分 (专家/Expert)**: **门槛极高，极其罕见**。必须满足以下**至少一项**: \n"
    "    - **行业影响力**: 是**行业知名人物**、技术大会讲师、畅销书作者、标准制定者。\n"
    "    - **职位级别**: 在任何规模的公司担任**总监、首席、VP**等高级决策角色。\n"
    "    - **开源/学术贡献**: 对知名开源项目有**核心贡献 (Committer/PMC)**，或在顶级期刊/会议上发表过相关论文。\n\n"
    "### 背景因素检查表 (用于辅助判断加减分)\n"
    "- **教育背景**: \n"
    "    - **学历**: 博士 > 硕士 > 本科。博士学历在相关研究领域有显著加分倾向。\n"
    "    - **学校**: 顶尖院校 (全球Top 50, C9) > 知名院校 (985/211) > 普通院校。顶尖院校背景为理论性强的技能提供强力支撑。\n"
    "- **工作背景**: \n"
    "    - **公司**: 顶级大厂 > 知名企业 > 中小型公司。大厂背景增加项目经验可信度。\n"
    "    - **年限**: 5年以上相关经验是“精通”的必要条件之一，但不是充分条件。10年以上是“专家”的参考门槛。\n"
    "    - **职位**: 总监/首席 > 经理/高级 > 普通/初级。职位高低直接关联职责和影响力。"
)

SYSTEM_PROMPT_SCORE = (
    "你是一位顶级的AI职业技能评估专家，以严格和精确著称。你的任务是基于用户简历，为【待评分标签列表】中的每一个标签进行1-5分的熟练度评估。\n\n"
    f"{COMMON_SCORING_RULES_V4}\n\n"
    "## 最终输出指令 (ABSOLUTE REQUIREMENT - NON-NEGOTIABLE)\n\n"
    "1.  **格式**: 你的回答**只能**包含 `标签:分数` 对，并用**单个空格**分隔。**绝对禁止**任何其他文字、符号、换行、标题、解释、或任何形式的思考过程。\n"
    "2.  **示例 (正确)**: `Java:4 Spring Boot:3 MySQL:3`\n"
    "3.  **示例 (错误)**: `1. Java:4`, `好的，这是评分：...`, `Java: 4` (冒号后多空格), `Java:3 #根据规则判定为熟练`\n"
    "**任何偏离上述格式的回答都将被视为完全失败，必须严格遵守。**"
)

SYSTEM_PROMPT_ADD = (
    "你是一位顶级的AI职业技能评估专家，以严格和精确著称。你的任务是基于用户简历，从【可选标签列表】中，选择若干新的、最相关的技能标签，并进行1-5分的熟练度评估。\n\n"
    "## 核心选择指令\n\n"
    "- **避免重复**: 你选择的标签**绝对不能**出现在【已有标签列表】中。\n"
    "- **唯一来源**: 你的选择**必须**严格来自于【可选标签列表】。\n"
    "- **精确匹配**: 你选择的标签文本，必须与列表中的原文**一字不差**。\n"
    "- **数量要求**: 请正好选择用户指令中要求的 **N** 个新标签。\n\n"
    f"{COMMON_SCORING_RULES_V4}\n\n"
    "## 最终输出指令 (ABSOLUTE REQUIREMENT - NON-NEGOTIABLE)\n\n"
    "1.  **格式**: 你的回答**只能**包含 `标签:分数` 对，并用**单个空格**分隔。**绝对禁止**任何其他文字、符号、换行、标题、解释、或任何形式的思考过程。\n"
    "2.  **示例 (正确)**: `机器学习:4 Python:3`\n"
    "3.  **示例 (错误)**: `好的，新增标签如下：...`, `* 机器学习:4`, `机器学习:4 (因为用户是博士)`\n"
    "**任何偏离上述格式的回答都将被视为完全失败，必须严格遵守。**"
)

def call_llm(system_prompt: str, user_prompt: str, api_key_manager: APIKeyManager) -> str:
    """调用 OpenAI API，使用 API key 管理器获取可用的 key"""
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }
    
    for attempt in range(1, MAX_RETRY + 1):
        api_key = api_key_manager.get_key()
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(API_URL, headers=headers, json=body, timeout=TIMEOUT_S)
            response.raise_for_status()
            data = response.json()
            
            if not data.get('choices') or not data['choices'][0].get('message') or 'content' not in data['choices'][0]['message']:
                raise KeyError("LLM响应中缺少'content'字段")
            
            return data['choices'][0]['message']['content'].strip()
            
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else None
            if status_code == 401:
                logging.warning(f"API key 认证失败 (第 {attempt}/{MAX_RETRY} 次): {e}")
            elif status_code == 429:
                logging.warning(f"API 请求频率限制 (第 {attempt}/{MAX_RETRY} 次): {e}")
                if attempt < MAX_RETRY:
                    time.sleep(2 ** attempt)  # 指数退避
            else:
                logging.warning(f"LLM HTTP 请求失败 (第 {attempt}/{MAX_RETRY} 次): {e}")
        except requests.exceptions.RequestException as e:
            logging.warning(f"LLM 请求失败 (第 {attempt}/{MAX_RETRY} 次): {e}")
        except (KeyError, IndexError) as e:
            logging.warning(f"LLM 响应格式错误 (第 {attempt}/{MAX_RETRY} 次): {e}")
        except Exception as e:
            logging.warning(f"LLM 调用时发生未知错误 (第 {attempt}/{MAX_RETRY} 次): {e}", exc_info=True)
        
        if attempt < MAX_RETRY:
            time.sleep(2 ** attempt)  # 指数退避
    
    return ""

# --- 模块 4: 核心业务逻辑 (Core Business Logic) ---

def parse_existing_tags(tag_string: str) -> List[Tag]:
    """
    鲁棒地解析格式为 "标签,分数,来源 | ..." 的字符串。
    """
    if not isinstance(tag_string, str) or not tag_string.strip():
        return []
    
    parsed_tags = []
    # 按 | 分割每个标签单元
    tag_units = [unit.strip() for unit in tag_string.split('|') if unit.strip()]
    
    for unit in tag_units:
        parts = [p.strip() for p in unit.split(',')]
        try:
            name = parts[0]
            # 分数可能是空或无效值，给个默认值0
            score = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            # 来源可能是空，给个默认值 'HM'
            source = parts[2] if len(parts) > 2 and parts[2] else 'HM'
            
            if name: # 必须要有标签名
                parsed_tags.append(Tag(name=name, score=score, source=source))
        except (IndexError, ValueError) as e:
            logging.warning(f"解析标签单元 '{unit}' 时出错，已跳过。错误: {e}")
            continue
            
    return parsed_tags

def format_tags_for_csv(tags: List[Tag]) -> str:
    """将Tag对象列表格式化为CSV字符串"""
    return " | ".join([f"{t.name} , {t.score} , {t.source}" for t in tags])

# 正则表达式现在更严格，只匹配 "标签:分数" 之间有单个空格或无空格的情况
# 这有助于过滤掉带有额外解释的行
_TAG_SCORE_RE = re.compile(r"([^:：\s]+?)\s*[:：]\s*([1-5])(?=\s|$)")

def parse_llm_response(reply: str, valid_tags: Set[str]) -> List[Tuple[str, int]]:
    """
    解析LLM返回的 "标签:分数" 格式的文本，提取有效的(标签, 分数)对。
    V4: 增强对非标准输出的过滤。
    """
    # 预处理：移除可能存在的Markdown标记和多余的空白字符
    reply = reply.replace('**', '').replace('`', '').strip()

    parsed_pairs = []
    # 查找所有匹配项
    matches = _TAG_SCORE_RE.findall(reply)
    
    # 检查是否有不应该出现的内容。如果除了匹配项和空格外还有其他字符，说明格式错误。
    expected_str = " ".join([f"{m[0]}:{m[1]}" for m in matches])
    if reply != expected_str and len(matches) > 0:
         logging.warning(f"LLM响应包含非标准字符，可能导致解析不全。原始回复: '{reply}'")

    for tag, score in matches:
        cleaned_tag = tag.strip()
        if cleaned_tag in valid_tags:
            parsed_pairs.append((cleaned_tag, int(score)))
    
    seen = set()
    unique_pairs = []
    for t, s in parsed_pairs:
        if t not in seen:
            unique_pairs.append((t, s))
            seen.add(t)
    return unique_pairs

def build_profile_text(profile_rows: List[Dict]) -> str:
    """构建通用的用户简历文本部分"""
    profile_lines = []
    for p in profile_rows:
        company = p.get('work_company', '')
        position = p.get('work_position', '')
        start_date = p.get('work_start_date', '')
        end_date = p.get('work_end_date', '')
        description = p.get('work_description', '')
        school = p.get('edu_school', '')
        major = p.get('edu_major', '')
        edu_start = p.get('edu_start_date', '')
        edu_end = p.get('edu_end_date', '')

        if p.get('exp_type') == 'WORK':
            profile_lines.append(f"工作经历: {company} / {position} ({start_date}~{end_date})\n描述: {description}")
        else:
            profile_lines.append(f"教育背景: {school} / {major} ({edu_start}~{edu_end})")
    
    return "### 用户简历信息\n\n" + "\n---\n".join(profile_lines)

def process_single_user(
    uid: int,
    group_df: pd.DataFrame,
    all_tags_dict: Dict[str, Set[str]],
    existing_tags_str: str,
    target_tag_count: int,
    api_key_manager: APIKeyManager
) -> Dict:
    try:
        logging.info(f"--- 正在处理 UID: {uid} ---")
        profile_rows = group_df.to_dict('records')

        # 确定用户的候选标签池
        user_work_lv3s = {str(row['work_lv3_name']) for row in profile_rows if row['exp_type'] == 'WORK' and pd.notna(row.get('work_lv3_name')) and str(row.get('work_lv3_name')).strip()}
        if not user_work_lv3s:
            logging.warning(f"跳过 UID {uid}: 无法确定任何有效的三级分类。")
            return {}
        
        candidate_tags_for_user: Set[str] = {tag for lv3 in user_work_lv3s for tag in all_tags_dict.get(lv3, set())}
        if not candidate_tags_for_user:
            logging.warning(f"跳过 UID {uid}: 其关联的三级类 '{','.join(user_work_lv3s)}' 在官方标签库中均无对应标签。")
            return {}

        # 1. 解析已有的标签
        current_tags: List[Tag] = parse_existing_tags(existing_tags_str)
        logging.info(f"UID {uid}: 解析到 {len(current_tags)} 个已有标签。")

        # 2. 【任务一】为没有分数的标签打分
        tags_to_score = [tag for tag in current_tags if tag.score == 0 and tag.name in candidate_tags_for_user]
        if tags_to_score:
            logging.info(f"发现 {len(tags_to_score)} 个需要评分的标签: {[t.name for t in tags_to_score]}")
            profile_text = build_profile_text(profile_rows)
            user_prompt_score = (
                f"{profile_text}\n\n"
                "### 任务详情\n\n"
                f"请为以下【待评分标签列表】中的每个标签打分。\n"
                f"【待评分标签列表】: {', '.join([t.name for t in tags_to_score])}"
            )
            llm_reply = call_llm(SYSTEM_PROMPT_SCORE, user_prompt_score, api_key_manager)
            scored_pairs = parse_llm_response(llm_reply, {t.name for t in tags_to_score})
            
            if scored_pairs:
                logging.info(f"LLM评分返回: '{llm_reply}' | 解析出 {len(scored_pairs)} 个有效评分。")
                score_map = dict(scored_pairs)
                # 更新分数
                updated_tags = []
                for tag in current_tags:
                    if tag.name in score_map:
                        updated_tags.append(tag._replace(score=score_map[tag.name], source='AI'))
                    else:
                        updated_tags.append(tag)
                current_tags = updated_tags
            else:
                logging.warning(f"LLM未能对标签进行有效评分，返回: '{llm_reply}'")

        # 3. 【任务二】如果标签数量不足，补充新标签
        num_to_add = target_tag_count - len(current_tags)
        if num_to_add > 0:
            logging.info(f"标签数量不足 {target_tag_count}，需要补充 {num_to_add} 个新标签。")
            
            existing_tag_names = {t.name for t in current_tags}
            # 从候选标签中排除已有的
            available_candidate_tags = sorted(list(candidate_tags_for_user - existing_tag_names))
            
            if not available_candidate_tags:
                logging.warning(f"UID {uid}: 没有可供选择的新标签了。")
            else:
                profile_text = build_profile_text(profile_rows)
                user_prompt_add = (
                    f"{profile_text}\n\n"
                    "### 任务详情\n\n"
                    f"1. **【已有标签列表】**: {', '.join(existing_tag_names) if existing_tag_names else '无'}\n"
                    f"2. **【可选标签列表】**: {', '.join(available_candidate_tags)}\n\n"
                    f"### 你的任务\n"
                    f"请严格遵循系统指令，从【可选标签列表】中选出 **{num_to_add}** 个新的标签并评分。"
                )
                llm_reply = call_llm(SYSTEM_PROMPT_ADD, user_prompt_add, api_key_manager)
                new_tagged_pairs = parse_llm_response(llm_reply, set(available_candidate_tags))
                
                if new_tagged_pairs:
                    logging.info(f"LLM新增标签返回: '{llm_reply}' | 解析出 {len(new_tagged_pairs)} 个新标签。")
                    for name, score in new_tagged_pairs[:num_to_add]: # 只取需要的数量
                        current_tags.append(Tag(name=name, score=score, source='AI'))
                else:
                    logging.warning(f"LLM未能生成有效的新标签，返回: '{llm_reply}'")

        # 4. 格式化最终结果并返回
        final_tag_string = format_tags_for_csv(current_tags)
        logging.info(f"UID {uid}: 处理完成。最终标签: {final_tag_string}")
        return {
            "uid": uid,
            "tags": final_tag_string
        }
        
    except Exception as e:
        logging.error(f"处理 UID {uid} 时发生未知严重错误: {e}", exc_info=True)
        return {}

# --- 模块 5: 主程序入口 (Main Execution) ---

def process_user_wrapper(args):
    """包装函数，用于并行处理单个用户"""
    uid, group_df, all_tags_dict, existing_tags_str, target_tag_count, api_key_manager = args
    try:
        result = process_single_user(
            uid, group_df, all_tags_dict, existing_tags_str, target_tag_count, api_key_manager
        )
        return uid, result, None
    except Exception as e:
        logging.error(f"处理 UID {uid} 时发生错误: {e}", exc_info=True)
        return uid, None, e

def main(target_tag_count: int):
    # 步骤 1: 加载和预处理所有数据
    user_df, official_tags, existing_tags_data = load_and_preprocess_data()
    
    # 步骤 1.5: 加载 API keys
    api_keys = load_api_keys(API_KEY_FILE)
    api_key_manager = APIKeyManager(api_keys)
    
    # 步骤 2: 计算关系、排序并选取Top N个用户
    uids_to_process = calculate_relationships_and_sort(user_df, TOP_N)
    
    if not uids_to_process:
        logging.warning("没有可处理的用户，程序即将退出。")
        return

    # 步骤 3: 并行处理选定的用户进行打标签实验
    final_results = []
    total_users = len(uids_to_process)
    logging.info(f"模块 4: 开始并行处理 {total_users} 位用户，目标标签数为 {target_tag_count}，使用 {MAX_WORKERS} 个并行线程...")
    
    all_processed_uids = set()
    
    # 准备任务列表
    tasks = []
    for uid in uids_to_process:
        user_group_df = user_df[user_df['uid'] == uid]
        if user_group_df.empty:
            logging.warning(f"在主表中找不到 UID {uid} 的信息，跳过。")
            continue
        
        existing_tags_str = existing_tags_data.get(uid, "")
        tasks.append((uid, user_group_df, official_tags, existing_tags_str, target_tag_count, api_key_manager))
    
    # 使用线程池并行处理
    completed_count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有任务
        future_to_uid = {
            executor.submit(process_user_wrapper, task): task[0] 
            for task in tasks
        }
        
        # 收集结果
        for future in as_completed(future_to_uid):
            uid, result, error = future.result()
            all_processed_uids.add(uid)
            completed_count += 1
            
            if error:
                logging.error(f"UID {uid} 处理失败: {error}")
            elif result:
                final_results.append(result)
                logging.info(f"UID {uid} 处理完成。进度: {completed_count}/{len(tasks)}")
            else:
                logging.warning(f"UID {uid} 处理返回空结果")
            
            if completed_count % 10 == 0:
                logging.info(f"--- 完成度: {completed_count}/{len(tasks)} ---")

    # 将未被处理但存在于旧文件中的用户数据也添加回来，防止数据丢失
    for uid, tags in existing_tags_data.items():
        if uid not in all_processed_uids:
            final_results.append({"uid": uid, "tags": tags})
            logging.info(f"保留了未处理的 UID {uid} 的旧数据。")

    if not final_results:
        logging.warning("本次运行没有产生任何有效结果，不生成文件。")
        return

    # 步骤 4: 保存最终结果
    logging.info(f"模块 5: 全部用户处理完毕，正在保存结果到 {OUTPUT_CSV}...")
    result_df = pd.DataFrame(final_results)
    result_df.sort_values('uid', inplace=True) # 按uid排序，方便查看
    
    try:
        # 覆盖写入
        result_df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
        logging.info(f"✅ 任务圆满完成！结果已成功保存到：{OUTPUT_CSV}")
    except Exception as e:
        logging.critical(f"保存结果文件失败: {e}", exc_info=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="使用LLM为用户简历智能打标签、评分并补充标签。")
    parser.add_argument(
        '-n', '--num-tags',
        type=int,
        default=5,  # 默认目标标签数为5
        help='指定每个用户最终应拥有的目标标签数量。'
    )
    args = parser.parse_args()
    
    main(target_tag_count=args.num_tags)
