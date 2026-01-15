
import json
import re
import time
from pathlib import Path
from typing import List, Dict, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import pandas as pd
import requests

ROOT_DIR = Path(__file__).resolve().parent
API_KEY_FILE = ROOT_DIR / "API_key-openai.md"


# 全局配置
def load_api_keys(file_path: Path = API_KEY_FILE) -> List[str]:
    """从 API_key-openai.md 文件加载所有API key"""
    api_keys: List[str] = []
    if not file_path.exists():
        raise FileNotFoundError(f"未找到 API key 文件: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 2:
                key = parts[-1].strip('"\'')
                if key.startswith('sk-'):
                    api_keys.append(key)
            elif line.startswith('sk-'):
                api_keys.append(line)
    if not api_keys:
        raise ValueError(f"在 {file_path} 中未找到任何有效的 OpenAI API key")
    print(f"[INFO] 成功加载 {len(api_keys)} 个API key")
    return api_keys


# 加载所有API key
API_KEYS = load_api_keys()

API_URL = "https://api.openai.com/v1/chat/completions"
MODEL_NAME = "gpt-5-mini"  # 使用 gpt-4 或 gpt-4-turbo 以获得最佳效果
TIMEOUT = 90  
MAX_RETRY = 3
MAX_WORKERS = min(len(API_KEYS), 10)  # 并行工作线程数

# API key轮询锁
_api_key_lock = Lock()
_api_key_index = 0

def get_next_api_key() -> str:
    """轮询获取下一个API key"""
    global _api_key_index
    with _api_key_lock:
        key = API_KEYS[_api_key_index % len(API_KEYS)]
        _api_key_index += 1
        return key

# 输入 / 输出文件
TAGS_CSV = ROOT_DIR / "all_labels copy.csv"
USER_DATA_CSV = ROOT_DIR / "merged_user_descriptions.csv"
OUTPUT_CSV = ROOT_DIR / "new_labels_list.csv"  # 输出文件名

# 数据加载与预处理 
def read_csv_with_encoding(file_path: Path, **kwargs):
    """尝试多种编码和解析选项读取CSV文件"""
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'utf-8-sig', 'latin1']
    last_error = None
    
    # 合并用户提供的kwargs
    csv_options = kwargs.copy()
    
    for encoding in encodings:
        try:
            # 首先尝试标准读取
            df = pd.read_csv(
                file_path, 
                encoding=encoding,
                **csv_options
            )
            print(f"[INFO] 成功使用 {encoding} 编码读取文件: {file_path.name}")
            return df
        except UnicodeDecodeError as e:
            last_error = e
            continue
        except (pd.errors.ParserError, pd.errors.EmptyDataError) as e:
            # 如果是解析错误，尝试更宽松的设置
            try:
                df = pd.read_csv(
                    file_path,
                    encoding=encoding,
                    on_bad_lines='skip',  # 跳过有问题的行
                    engine='python',  # 使用Python引擎，更宽松
                    **{k: v for k, v in csv_options.items() if k not in ['on_bad_lines', 'engine']}
                )
                print(f"[INFO] 成功使用 {encoding} 编码（Python引擎，跳过错误行）读取文件: {file_path.name}")
                return df
            except Exception as e2:
                last_error = e2
                continue
        except Exception as e:
            last_error = e
            continue
    
    raise ValueError(f"无法读取文件 {file_path.name}，已尝试所有编码: {encodings}。最后错误: {last_error}")

print("[INFO] 开始加载和预处理数据...")

try:
    # 加载标签数据
    tags_df = read_csv_with_encoding(TAGS_CSV)
    if not {'level_3rd', 'skill_type', 'tags'}.issubset(tags_df.columns):
        raise ValueError(f"{TAGS_CSV.name} 必须包含 'level_3rd', 'skill_type', 'tags' 三列")
    print(f"[INFO] 成功加载 {len(tags_df)} 行标签数据从 {TAGS_CSV.name}")

    # 加载用户工作描述数据
    user_df = read_csv_with_encoding(USER_DATA_CSV)
    if not {'exp_type', 'work_lv3_name', 'work_description'}.issubset(user_df.columns):
        raise ValueError(f"{USER_DATA_CSV.name} 必须包含 'exp_type', 'work_lv3_name', 'work_description' 列")
    print(f"[INFO] 成功加载 {len(user_df)} 行用户数据从 {USER_DATA_CSV.name}")

except FileNotFoundError as e:
    print(f"[ERROR] 文件未找到: {e}. 请确保脚本与数据文件在同一目录下。")
    exit()
except ValueError as e:
    print(f"[ERROR] {e}")
    exit()
except Exception as e:
    print(f"[ERROR] 读取文件时发生未知错误: {e}")
    exit()

# 预处理：按三级类分组，聚合工作描述
print("[INFO] 正在聚合工作描述...")
work_descriptions: Dict[str, str] = {}
work_df = user_df[user_df['exp_type'] == 'WORK'].copy()
work_df.dropna(subset=['work_lv3_name', 'work_description'], inplace=True)

# 对每个三级分类，拼接其所有的工作描述
# 为避免 prompt 过长，这里限制每个岗位的总描述长度
MAX_DESC_LENGTH = 4000
for lv3_name, group in work_df.groupby('work_lv3_name'):
    # 将所有描述用换行符合并，并截断到最大长度
    full_desc = "\n---\n".join(group['work_description'].astype(str).unique())
    work_descriptions[lv3_name] = full_desc[:MAX_DESC_LENGTH]

print(f"[INFO] 数据预处理完成，聚合了 {len(work_descriptions)} 个岗位的真实工作描述。")

# 请求封装（HEADERS将在每次调用时动态生成）

SYSTEM_MSG = (
    "你是顶级的行业技能分析专家，任务是根据市场当前需求，为职业技能列表补充新的、重要的技能标签。\n"
    "你必须严格遵守以下规则：\n"
    "1. **核心任务**: 分析【现有标签列表】和大量【相关工作内容描述示例】，识别出当前至关重要但尚未包含在列表中的新技能。\n"
    "2. **分析依据**: 你建议的每个新标签，都必须是基于对【相关工作内容描述示例】中反复出现、强调的工具、技术或职责的提炼，并结合你对该行业当前技术趋势的理解。\n"
    "3. **新增要求**:\n"
    "   - **不重复**: 新增的标签绝对不能与【现有标签列表】中的任何一个重复或含义高度重合。\n"
    "   - **相关性**: 新增的标签必须与给定的【技能类型】高度相关。\n"
    "   - **必要性**: 如果一个标签可添加可不添加，则不应出现在新增标签列表中。\n"
    "   - **命名风格**: 新增标签的命名应简洁、专业，并与【现有标签列表】的风格保持一致。\n"
    "   - **数量限制**: 新增标签的数量不宜过多，必须不超过3个且不超过PROMPT给出的【现有标签列表】数量的一半。\n"
    "4. **输出格式**: 你的回答必须是一个严格的 JSON 对象，且只包含一个键 'add'，其值为一个字符串列表。例如： `{\"add\": [\"新标签1\", \"新标签2\"]}`。\n"
    "5. **禁止项**: 绝对禁止输出任何 JSON 格式之外的文字、解释、或任何形式的寒暄。"
)

def call_llm(prompt: str, api_key: str = None) -> str:
    api_key = api_key or get_next_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_MSG},
            {"role": "user", "content": prompt}
        ]
    }
    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = requests.post(API_URL, headers=headers, json=payload, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()['choices'][0]['message']['content'].strip()
        except requests.exceptions.RequestException as e:
            print(f"  [WARN] LLM 请求失败 (第 {attempt}/{MAX_RETRY} 次): {e}")
        except (KeyError, IndexError) as e:
            print(f"  [WARN] LLM 响应格式错误 (第 {attempt}/{MAX_RETRY} 次): {e}")
        
        if attempt < MAX_RETRY:
            time.sleep(2 * attempt) # 指数退避
    return "" # 所有重试失败后返回空字符串

# JSON 解析
def safe_json_load(text: str) -> Dict[str, List[str]]:
    try:
        match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            text = match.group(1)
        return json.loads(text)
    except json.JSONDecodeError:
        return {}

# 处理单个分组的函数（用于并行处理）
def process_single_group(args: Tuple) -> Dict:
    """处理单个标签分组"""
    i, level_3rd, skill_type, group, work_descriptions, total_groups = args
    
    print(f"\n--- [{i+1}/{total_groups}] 正在处理: {level_3rd} / {skill_type} ---")
    
    # 整理当前分组的原始标签
    original_tags = sorted({t.strip() for ts in group['tags'] for t in str(ts).split('|_|') if t.strip()})
    if not original_tags:
        print(f"  [INFO] 该分组无有效原始标签，跳过。")
        return None
    
    # 获取对应的工作描述
    descriptions = work_descriptions.get(level_3rd)
    if not descriptions:
        print(f"  [WARN] 未找到 '{level_3rd}' 对应的任何工作描述，AI将仅根据通用知识进行推荐。")
        descriptions = "无。请仅根据通用行业知识进行判断。"

    # 构建 Prompt
    prompt = (
        f"职业岗位（三级类）：{level_3rd}\n"
        f"技能类型：{skill_type}\n\n"
        f"【现有标签列表】:\n{', '.join(original_tags)}\n\n"
        f"【相关工作内容描述示例】:\n{descriptions}\n\n"
        "请严格遵照系统指令，分析以上信息，并仅以指定的 JSON 格式返回你建议新增的技能标签。"
    )

    # 调用 LLM（使用轮询的API key）
    api_key = get_next_api_key()
    response_text = call_llm(prompt, api_key)

    if not response_text:
        print(f"  [ERROR] LLM 无有效返回，跳过此分组。")
        return None
    
    print(f"  [DEBUG] LLM 原始返回: {response_text[:200]}...")

    # 解析结果
    parsed_json = safe_json_load(response_text)
    add_tags = parsed_json.get('add', [])

    if not isinstance(add_tags, list):
        print(f"  [ERROR] JSON 'add' 字段非列表格式，跳过。")
        add_tags = []

    # 清理和去重
    add_tags = sorted(list({t.strip() for t in add_tags if t.strip()}))
    
    print(f"  [INFO] 原始标签数: {len(original_tags)} | AI建议新增: {len(add_tags)} 个 -> {add_tags if add_tags else '无'}")

    # 返回结果
    return {
        'level_3rd': level_3rd,
        'skill_type': skill_type,
        'original_tags': '|_|'.join(original_tags),
        'suggested_add_tags': '|_|'.join(add_tags),
        'original_cnt': len(original_tags),
        'add_cnt': len(add_tags),
        '_original_idx': i  # 用于排序
    }

# 主流程（并行版本）
results: List[Dict] = []
groups_list = list(tags_df.groupby(['level_3rd', 'skill_type']))
total_groups = len(groups_list)
print(f"\n[INFO] 开始处理 {total_groups} 个标签分组（使用 {MAX_WORKERS} 个并行线程）...")

# 准备任务列表
tasks = [
    (i, level_3rd, skill_type, group, work_descriptions, total_groups)
    for i, ((level_3rd, skill_type), group) in enumerate(groups_list, 1)
]

# 使用线程池并行处理
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    future_to_task = {executor.submit(process_single_group, task): task for task in tasks}
    
    for future in as_completed(future_to_task):
        try:
            result = future.result()
            if result is not None:
                results.append(result)
        except Exception as e:
            print(f"  [ERROR] 处理分组失败: {e}")
            task = future_to_task[future]
            i, level_3rd, skill_type, group, _, _ = task
            print(f"  [ERROR] 失败的分组: {level_3rd} / {skill_type}")

# 按原始顺序排序
results.sort(key=lambda x: x.get('_original_idx', 0))
# 移除临时索引字段
for result in results:
    result.pop('_original_idx', None)

# 输出到文件
if results:
    print(f"\n[INFO] 全部处理完毕，正在将 {len(results)} 条结果写入 → {OUTPUT_CSV}")
    result_df = pd.DataFrame(results)
    result_df = result_df[[
        'level_3rd', 'skill_type', 'original_cnt', 'add_cnt', 
        'original_tags', 'suggested_add_tags'
    ]]
    result_df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig') 
    print(f"[SUCCESS] ✅ 任务完成！结果已成功保存到：{OUTPUT_CSV}")
else:
    print("\n[INFO] 本次运行没有产生任何结果。")
