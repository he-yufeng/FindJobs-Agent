#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
bytedance_jobs.json 智能结构化脚本

功能概述：
1. 调用 OpenAI LLM，对岗位进行学历/专业/技能/岗位族分类分析。
2. 技能标签严格来源于 all_labels.csv，并沿用 tag_rate.py 的评分标准。
3. 通过 user_descriptions.csv 动态构建中国科技行业常用的一级/二级岗位族谱（约200个二级岗位）。
4. 将结构化结果与原始岗位字段合并，输出到新的 CSV。

使用示例：
    python job_agent.py ^
        --jobs-file bytedance_jobs.json ^
        --output-file bytedance_jobs_enriched.csv ^
        --taxonomy-file tech_taxonomy.json ^
        --target-skill-count 6
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import pandas as pd
import requests

from llm_utils import apply_temperature_strategy

try:
    # 直接复用 tag_rate 中的 API Key 管理器与评分规则，保证一致性
    from tag_rate import (
        APIKeyManager,
        COMMON_SCORING_RULES_V4,
        format_tags_for_csv,
        load_api_keys,
    )
except ImportError as exc:  # pragma: no cover
    raise ImportError("请确保 tag_rate.py 可用，并与本脚本位于同一目录。") from exc


# --- 全局默认配置 ---
ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_JOBS_FILE = ROOT_DIR / "bytedance_jobs copy.json"
DEFAULT_LABELS_FILE = ROOT_DIR / "all_labels.csv"
DEFAULT_USER_DESC_FILE = ROOT_DIR / "user_descriptions.csv"
DEFAULT_TAXONOMY_FILE = ROOT_DIR / "tech_taxonomy.json"
DEFAULT_OUTPUT_FILE = ROOT_DIR / "bytedance_jobs_enriched.csv"
DEFAULT_API_KEY_FILE = ROOT_DIR / "API_key-openai.md"

API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-5-mini"  # 与 tag_rate 保持一致，避免模型名不被支持
REQUEST_TIMEOUT = 120
MAX_LLM_RETRY = 3
MAX_WORKERS = 10  # 并行处理的最大线程数（对应多个 API keys）

DEGREE_ORDER = ["大专", "本科", "硕士", "博士"]
PRIORITY_VALUES = {"必须", "优先"}

PROGRAM_CACHE_FILE = ROOT_DIR / "program_context_cache.json"

# --- 岗位强度信号配置 ---
SIGNAL_RULES = [
    {
        "label": "博士学位",
        "patterns": [r"博士在读", r"博士学位", r"\bPhD\b", r"Doctorate", r"博士后"],
        "impact": "岗位面向博士/博士后，核心科研技能需达到专家水平。",
        "weight": 4,
        "tier": "research",
    },
    {
        "label": "旗舰/人才计划",
        "patterns": [
            r"Top\s+Seed",
            r"Top\s+Program",
            r"Talent\s+Program",
            r"旗舰计划",
            r"人才计划",
            r"精英计划",
            r"领军计划",
        ],
        "impact": "该岗位属于旗舰/人才计划，面向高价值候选人，需要先进技能沉淀。",
        "weight": 3,
        "tier": "flagship",
    },
    {
        "label": "国际/跨国实验室",
        "patterns": [
            r"国际",
            r"跨国",
            r"全球",
            r"新加坡",
            r"美国",
            r"欧洲",
            r"实验室",
            r"lab",
        ],
        "impact": "岗位涉及国际实验室协作，默认要求全球领先的研究能力。",
        "weight": 2,
        "tier": "research",
    },
    {
        "label": "顶级会议/科研成果",
        "patterns": [
            r"\bACL\b",
            r"\bEMNLP\b",
            r"\bNAACL\b",
            r"\bNeurIPS\b",
            r"\bICML\b",
            r"\bICLR\b",
            r"\bCVPR\b",
            r"\bKDD\b",
            r"\bAAAI\b",
        ],
        "impact": "岗位要求在顶级会议发表成果，意味着技能须达到行业前沿。",
        "weight": 3,
        "tier": "research",
    },
    {
        "label": "前沿大模型/Agent研究",
        "patterns": [
            r"通用大模型",
            r"世界模型",
            r"AI\s*Infra",
            r"自主\s*Agent",
            r"复杂推理",
            r"多模态",
            r"量化评测",
            r"可扩展监督",
            r"大规模数据合成",
        ],
        "impact": "岗位聚焦前沿 LLM/Agent 研究，需要高阶算法与工程能力。",
        "weight": 2,
        "tier": "research",
    },
]

INTENSITY_LEVELS = [
    {"label": "flagship_research", "min_score": 9, "base_score": 5, "description": "旗舰科研岗"},
    {"label": "research", "min_score": 6, "base_score": 4, "description": "科研型岗位"},
    {"label": "advanced", "min_score": 3, "base_score": 3, "description": "高级岗位"},
    {"label": "standard", "min_score": 0, "base_score": 3, "description": "常规岗位"},
]

PROGRAM_TERM_PATTERNS = [
    r"[A-Z][A-Za-z]+\s+Program",
    r"[A-Z][A-Za-z]+\s+Plan",
    r"Top\s+Seed",
    r"Talent\s+Program",
    r"Flagship\s+Program",
    r"[A-Za-z]+\s+Lab",
    r"[A-Za-z]+\s+Research\s+Center",
]

LOW_INFORMATION_SKILLS = {
    "AI",
    "人工智能",
    "技术",
    "数学",
    "计算机",
    "科研",
    "能力",
    "技能",
}

GENERIC_SKILL_HINTS = {
    "AI": ["大模型", "算法", "人工智能", "智能体"],
    "人工智能": ["人工智能算法", "机器学习"],
    "数学": ["概率论", "统计学习", "线性代数"],
    "计算机": ["计算机视觉", "计算机科学"],
    "技术": ["工程能力", "系统设计"],
}

_TAG_SCORE_RE = re.compile(r"([^:：\s]+?)\s*[:：]\s*([1-5])(?=\s|$)")


def parse_llm_response(reply: str, valid_tags: Set[str]) -> List[Tuple[str, int]]:
    """解析 LLM 返回的 `标签:分数` 文本"""
    if not reply:
        return []
    clean_reply = reply.replace("**", "").replace("`", "").strip()
    matches = _TAG_SCORE_RE.findall(clean_reply)
    parsed_pairs: List[Tuple[str, int]] = []
    for tag, score in matches:
        cleaned_tag = tag.strip()
        if cleaned_tag in valid_tags:
            parsed_pairs.append((cleaned_tag, int(score)))

    unique_pairs: List[Tuple[str, int]] = []
    seen = set()
    for t, s in parsed_pairs:
        if t not in seen:
            unique_pairs.append((t, s))
            seen.add(t)
    return unique_pairs


def normalize_text(text: Any) -> str:
    """移除空白并小写化，便于相似度计算。"""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return re.sub(r"\s+", "", text).lower()


def deduplicate(seq: Iterable[str]) -> List[str]:
    """保持顺序去重。"""
    seen = set()
    result = []
    for item in seq:
        if not item:
            continue
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def format_skill_string(skills: Sequence[Tuple[str, int]]) -> str:
    """格式化技能列表为 CSV 友好的字符串，与 tag_rate 输出保持一致。"""
    return " | ".join(f"{name} , {score} , AI" for name, score in skills)


class OpenAIClient:
    """基于 requests 的轻量封装，支持 JSON 强制输出。"""

    def __init__(
        self,
        api_key_manager: APIKeyManager,
        model: str = DEFAULT_MODEL,
        api_url: str = API_URL,
        timeout: int = REQUEST_TIMEOUT,
        max_retry: int = MAX_LLM_RETRY,
    ) -> None:
        self.api_key_manager = api_key_manager
        self.model = model
        self.api_url = api_url
        self.timeout = timeout
        self.max_retry = max_retry

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        target_temperature = 0.2
        adjusted_system_prompt, temp_param = apply_temperature_strategy(
            self.model, system_prompt, target_temperature
        )
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": adjusted_system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if temp_param is not None:
            body["temperature"] = temp_param
        if response_format:
            body["response_format"] = response_format

        for attempt in range(1, self.max_retry + 1):
            api_key = self.api_key_manager.get_key()
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            try:
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=body,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
                if content:
                    return content
                raise ValueError("LLM 响应为空或缺少 content 字段。")
            except requests.exceptions.HTTPError as err:
                # 尝试解析错误详情
                error_detail = ""
                try:
                    if err.response:
                        error_data = err.response.json()
                        error_detail = error_data.get("error", {}).get("message", "")
                except:
                    pass
                logging.warning(
                    "LLM HTTP 错误（第 %s/%s 次，key=%s）：%s - %s",
                    attempt,
                    self.max_retry,
                    api_key[-6:],
                    err,
                    error_detail or "无详细信息",
                )
                if attempt < self.max_retry:
                    time.sleep(2**attempt)
            except Exception as err:  # pragma: no cover
                logging.warning(
                    "LLM 调用失败（第 %s/%s 次，key=%s）：%s",
                    attempt,
                    self.max_retry,
                    api_key[-6:],
                    err,
                )
                if attempt < self.max_retry:
                    time.sleep(2**attempt)
        raise RuntimeError("LLM 多次重试后仍失败。")


class SkillRepository:
    """加载 all_labels.csv，并提供岗位技能候选集合。"""

    def __init__(self, labels_path: Path, max_level_candidates: int = 12) -> None:
        if not labels_path.exists():
            raise FileNotFoundError(f"未找到技能标签库: {labels_path}")
        self.labels_path = labels_path
        self.max_level_candidates = max_level_candidates
        self.level_to_tags: Dict[str, List[str]] = {}
        self._tag_sequence: List[str] = []
        self._load_labels()

    def _load_labels(self) -> None:
        df = pd.read_csv(self.labels_path).fillna("")
        for _, row in df.iterrows():
            lv3 = str(row["level_3rd"]).strip()
            tags_raw = str(row["tags"]).split("|_|")
            clean_tags = [t.strip() for t in tags_raw if t.strip()]
            if not lv3 or not clean_tags:
                continue
            self.level_to_tags.setdefault(lv3, []).extend(clean_tags)
            self._tag_sequence.extend(clean_tags)
        self.all_tags: List[str] = deduplicate(self._tag_sequence)
        # 选取一批常见标签作为兜底
        self.global_fallback_tags = self.all_tags[:150]

    def _level_similarity(self, text: str, level_name: str) -> float:
        text_norm = normalize_text(text)
        level_norm = normalize_text(level_name)
        if not text_norm or not level_norm:
            return 0.0
        score = SequenceMatcher(None, text_norm, level_norm).ratio()
        if level_norm in text_norm:
            score += 0.6
        return score

    def get_candidate_tags(
        self,
        job_title: str,
        job_text: str,
        special_program: str,
        limit: int = 80,
    ) -> List[str]:
        combined = f"{job_title or ''} {special_program or ''}"
        level_scores: List[Tuple[float, str]] = []
        for level_name in self.level_to_tags:
            score = self._level_similarity(combined, level_name)
            if score > 0.32:
                level_scores.append((score, level_name))
        level_scores.sort(reverse=True)
        selected_levels = [lvl for _, lvl in level_scores[: self.max_level_candidates]]

        candidates: List[str] = []
        for lvl in selected_levels:
            candidates.extend(self.level_to_tags.get(lvl, []))

        # 文本直接命中的标签
        text_norm = (job_text or "").lower()
        direct_hits = []
        hit_counter = 0
        for tag in self.all_tags:
            if hit_counter >= 40:
                break
            if tag.lower() in text_norm:
                direct_hits.append(tag)
                hit_counter += 1

        combined_list = candidates + direct_hits + self.global_fallback_tags
        deduped = deduplicate(combined_list)
        if len(deduped) < limit:
            return deduped
        return deduped[:limit]

    def validate_skill(self, skill_name: str) -> bool:
        return skill_name in self.all_tags


@dataclass
class Signal:
    label: str
    impact: str
    evidence: str
    weight: int


@dataclass
class Level2Entry:
    level1: str
    level2: str
    keywords: List[str]
    description: str


class KnowledgeRetriever:
    """检索 program/计划 名称的背景信息，并缓存结果"""

    def __init__(self, cache_file: Path):
        self.cache_file = cache_file
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, str]:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                logging.warning("无法读取 program cache，使用空缓存")
        return {}

    def _save_cache(self) -> None:
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.warning(f"保存 program cache 失败: {e}")

    def lookup(self, term: str) -> str:
        term_key = term.strip()
        if not term_key:
            return ""
        if term_key in self.cache:
            return self.cache[term_key]
        summary = self._fetch_from_duckduckgo(term_key)
        if summary:
            self.cache[term_key] = summary
            self._save_cache()
        return summary

    def lookup_terms(self, terms: List[str]) -> Dict[str, str]:
        results = {}
        for term in terms:
            summary = self.lookup(term)
            if summary:
                results[term] = summary
        return results

    def _fetch_from_duckduckgo(self, term: str) -> str:
        try:
            params = {
                "q": f"{term} 科技 招聘",
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
            }
            resp = requests.get("https://api.duckduckgo.com/", params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            summary = data.get("AbstractText") or ""
            if not summary:
                topics = data.get("RelatedTopics") or []
                for topic in topics:
                    if isinstance(topic, dict) and topic.get("Text"):
                        summary = topic["Text"]
                        break
            return summary.strip()
        except Exception as err:
            logging.debug(f"DuckDuckGo 检索失败: {err}")
            return ""


class JobSignalAnalyzer:
    """基于通用信号识别岗位强度"""

    def __init__(self):
        self.rule_patterns = []
        for rule in SIGNAL_RULES:
            compiled = [re.compile(pat, re.IGNORECASE) for pat in rule["patterns"]]
            self.rule_patterns.append({**rule, "compiled": compiled})

    def analyze(self, job: Dict[str, Any]) -> Dict[str, Any]:
        text = " ".join(
            [
                str(job.get("job_title", "")),
                str(job.get("job_description", "")),
                str(job.get("job_requirements", "")),
                str(job.get("special_program", "")),
            ]
        )
        signals: List[Signal] = []
        total_score = 0

        for rule in self.rule_patterns:
            if any(pattern.search(text) for pattern in rule["compiled"]):
                signal = Signal(
                    label=rule["label"],
                    impact=rule["impact"],
                    evidence=rule["label"],
                    weight=rule["weight"],
                )
                signals.append(signal)
                total_score += rule["weight"]

        intensity = self._determine_intensity(total_score)
        program_terms = self._extract_program_terms(job, text)

        return {
            "score": total_score,
            "level": intensity["label"],
            "level_description": intensity["description"],
            "base_score": intensity["base_score"],
            "signals": signals,
            "program_terms": program_terms,
        }

    def _determine_intensity(self, score: int) -> Dict[str, Any]:
        for level in INTENSITY_LEVELS:
            if score >= level["min_score"]:
                return level
        return INTENSITY_LEVELS[-1]

    def _extract_program_terms(self, job: Dict[str, Any], text: str) -> List[str]:
        terms = set()
        special = str(job.get("special_program", "")).strip()
        if special:
            terms.add(special)

        for pattern in PROGRAM_TERM_PATTERNS:
            matches = re.findall(pattern, text, flags=re.IGNORECASE)
            for match in matches:
                cleaned = match.strip()
                if cleaned:
                    terms.add(cleaned)

        return sorted(terms)


class SkillNormalizer:
    """对模型输出的技能进行归一化和泛化词替换"""

    @classmethod
    def normalize(
        cls,
        skills: List[Tuple[str, int]],
        candidate_tags: List[str],
    ) -> List[Tuple[str, int]]:
        normalized: List[Tuple[str, int]] = []
        seen: set = set()
        for name, score in skills:
            clean_name = name.strip()
            if not clean_name:
                continue
            new_name = cls._replace_generic(clean_name, candidate_tags)
            if not new_name:
                continue
            key = (new_name, score)
            if key not in seen:
                normalized.append((new_name, score))
                seen.add(key)
        return normalized

    @classmethod
    def _replace_generic(cls, name: str, candidate_tags: List[str]) -> Optional[str]:
        simple_name = name.replace(" ", "")
        if simple_name in LOW_INFORMATION_SKILLS:
            hints = GENERIC_SKILL_HINTS.get(name, GENERIC_SKILL_HINTS.get(simple_name, []))
            for hint in hints:
                for tag in candidate_tags:
                    if hint in tag and tag not in LOW_INFORMATION_SKILLS:
                        return tag
            return None
        return name


REVIEW_SYSTEM_PROMPT = (
    "你是一名资深的技能评审官，专门针对高强度岗位的技能评分进行复核。"
    "当岗位需求明确包含博士、旗舰计划、顶会成果等信号时，核心技能应达到 4-5 分。"
    "如果评分偏低，请根据信号给出更合理的分数。输出格式：`技能:分数`，仅输出需要调整的技能。"
)


class SkillReviewAgent:
    """根据岗位强度再次审查技能评分"""

    def __init__(self, llm_client: "OpenAIClient"):
        self.llm_client = llm_client

    def review(
        self,
        job_text: str,
        strength_info: Dict[str, Any],
        skills: List[Tuple[str, int]],
        parse_fn,
    ) -> List[Tuple[str, int]]:
        base_score = strength_info.get("base_score", 3)
        if base_score <= 3:
            return skills

        flagged = [(name, score) for name, score in skills if score < base_score]
        if not flagged:
            return skills

        signal_lines = ["- " + sig.impact for sig in strength_info.get("signals", [])] or ["- 无明显信号"]
        flagged_text = ", ".join([f"{name}:{score}" for name, score in flagged])
        user_prompt = (
            f"### 岗位文本\n{job_text}\n\n"
            f"### 岗位强度\n等级: {strength_info.get('level_description')} (基准分 >= {base_score})\n"
            f"信号:\n" + "\n".join(signal_lines) + "\n\n"
            f"### 当前低分技能\n{flagged_text}\n"
            "请判断这些技能是否需要提升分数，并输出新的 `技能:分数`，仅在需要调高时输出。"
        )

        try:
            reply = self.llm_client.chat(
                REVIEW_SYSTEM_PROMPT,
                user_prompt,
            )
        except Exception as err:
            logging.warning(f"技能复核失败，保持原评分: {err}")
            return skills

        adjustments = parse_fn(reply, {name for name, _ in flagged})
        if not adjustments:
            return skills

        adjustment_map = dict(adjustments)
        updated = []
        for name, score in skills:
            if name in adjustment_map and adjustment_map[name] > score:
                updated.append((name, adjustment_map[name]))
            else:
                updated.append((name, score))
        return updated


class TaxonomyManager:
    """构建并索引一级/二级岗位族。"""

    def __init__(
        self,
        taxonomy_path: Path,
        user_desc_path: Path,
        llm_client: OpenAIClient,
    ) -> None:
        self.taxonomy_path = taxonomy_path
        self.user_desc_path = user_desc_path
        self.llm_client = llm_client
        self.taxonomy: Dict[str, Any] = {}
        self.level2_index: List[Level2Entry] = []
        self._lock = threading.Lock()

    def ensure_taxonomy(self, force_rebuild: bool = False) -> None:
        if self.taxonomy and self.level2_index and not force_rebuild:
            return
        if self.taxonomy_path.exists() and not force_rebuild:
            logging.info("📂 加载已有岗位族谱: %s", self.taxonomy_path)
            self._load_from_disk()
            return
        logging.info("🔨 未找到岗位族谱文件，开始调用 LLM 构建...")
        taxonomy = self._build_via_llm()
        self.taxonomy = taxonomy
        self._prepare_index()
        self._save_to_disk()
        logging.info("✨ 岗位族谱构建完成！")

    def _load_from_disk(self) -> None:
        with open(self.taxonomy_path, "r", encoding="utf-8") as f:
            self.taxonomy = json.load(f)
        self._prepare_index()

    def _save_to_disk(self) -> None:
        """将岗位族谱保存到本地文件"""
        try:
            with open(self.taxonomy_path, "w", encoding="utf-8") as f:
                json.dump(self.taxonomy, f, ensure_ascii=False, indent=2)
            logging.info(f"💾 岗位族谱已保存到: {self.taxonomy_path}")
        except Exception as e:
            logging.error(f"❌ 保存岗位族谱失败: {e}")
            raise

    def _prepare_index(self) -> None:
        level2_entries: List[Level2Entry] = []
        for lvl1 in self.taxonomy.get("level1_categories", []):
            lvl1_name = lvl1.get("name", "")
            for lvl2 in lvl1.get("level2_roles", []):
                entry = Level2Entry(
                    level1=lvl1_name,
                    level2=lvl2.get("name", ""),
                    keywords=lvl2.get("keywords", []),
                    description=lvl2.get("description", ""),
                )
                level2_entries.append(entry)
        if not level2_entries:
            raise ValueError("岗位族谱文件格式不正确，缺少 level2_roles。")
        self.level2_index = level2_entries
        logging.info(
            "岗位族谱准备完成：%s 个一级分类，%s 个二级分类。",
            len(self.taxonomy.get("level1_categories", [])),
            len(self.level2_index),
        )

    def _build_via_llm(self) -> Dict[str, Any]:
        if not self.user_desc_path.exists():
            raise FileNotFoundError(
                f"无法构建岗位族谱：缺少数据源 {self.user_desc_path}"
            )
        logging.info("📊 正在加载用户描述数据...")
        df = pd.read_csv(self.user_desc_path)
        if "work_lv3_name" not in df.columns:
            raise ValueError("user_descriptions.csv 缺少 work_lv3_name 列。")
        freq = (
            df["work_lv3_name"]
            .dropna()
            .astype(str)
            .str.strip()
            .value_counts()
            .head(400)
        )
        logging.info(f"✅ 已提取 {len(freq)} 个岗位类型用于构建族谱")
        sample_payload = [
            {"name": name, "count": int(count)}
            for name, count in freq.to_dict().items()
        ]
        system_prompt = (
            "你是一名资深的人力市场分析师，熟悉中国互联网与科技行业岗位。"
            "请基于输入的岗位名称频次，构建稳定且覆盖度高的岗位族谱。"
            "**重要**：你必须生成约 180-220 个二级岗位，这是硬性要求。"
        )
        user_prompt = (
            "### 数据来源\n"
            "以下为科技行业真实岗位的顶层统计(名称+频次，仅供参考)：\n"
            f"{json.dumps(sample_payload[:100], ensure_ascii=False)}\n\n"
            "### 任务要求(必须严格遵守)\n"
            "1. 输出格式：JSON 对象，包含以下字段：\n"
            "   - version: 字符串，使用当前日期(格式：YYYY-MM-DD)\n"
            "   - level1_categories: 数组，每个元素包含：\n"
            "     * name: 一级分类名称(如：算法、后端、前端、数据、产品、运营、设计、测试、硬件、供应链、职能等)\n"
            "     * description: 一级分类描述\n"
            "     * level2_roles: 数组，包含该一级分类下的所有二级岗位\n"
            "   - level2_roles 数组中每个元素包含：\n"
            "     * name: 二级岗位名称(如：搜广推算法、Java工程师、前端开发工程师等)\n"
            "     * description: 二级岗位描述\n"
            "     * keywords: 数组，3-5个关键词用于匹配职位文本(如：['推荐', 'CTR', '特征'])\n\n"
            "2. **数量要求(关键)**：\n"
            "   - 一级分类数量：18-22 个\n"
            "   - **二级岗位总数：必须达到 180-220 个**\n"
            "   - 每个一级分类下平均应有 8-15 个二级岗位\n"
            "   - 热门方向(如算法、后端、前端、数据)应包含更多二级岗位(15-20个)\n"
            "   - 小众方向(如硬件、供应链)可包含较少二级岗位(5-10个)\n\n"
            "3. 覆盖要求：\n"
            "   - 必须覆盖：算法、后端、前端、数据、产品、运营、设计、测试、硬件、供应链、职能等主流方向\n"
            "   - 二级岗位命名需贴合中国科技行业常用叫法\n"
            "   - 参考数据中的岗位名称，但可以适当扩展和归纳\n\n"
            "4. 质量要求：\n"
            "   - keywords 必须精炼且具有区分度\n"
            "   - 二级岗位名称要具体，避免过于宽泛\n"
            "   - 确保不同一级分类下的二级岗位不重复\n\n"
            "5. **重要提醒**：\n"
            "   - 二级岗位总数少于 180 个将被视为不合格\n"
            "   - 请仔细计算每个一级分类下的二级岗位数量，确保总数达到要求\n"
            "   - 只输出 JSON，不要附加任何解释文字"
        )
        
        max_retries = 2
        for attempt in range(1, max_retries + 1):
            logging.info(f"🤖 正在调用 LLM 构建岗位族谱(第 {attempt}/{max_retries} 次尝试，这可能需要几十秒)...")
            try:
                response = self.llm_client.chat(
                    system_prompt,
                    user_prompt,
                    response_format={"type": "json_object"},
                )
                logging.info("✅ LLM 响应已收到，正在解析和验证...")
                taxonomy = json.loads(response)
                total_lvl2 = sum(
                    len(lvl1.get("level2_roles", []))
                    for lvl1 in taxonomy.get("level1_categories", [])
                )
                total_lvl1 = len(taxonomy.get("level1_categories", []))
                logging.info(f"📋 岗位族谱统计：{total_lvl1} 个一级分类，{total_lvl2} 个二级岗位")
                
                if total_lvl2 < 50:
                    if attempt < max_retries:
                        logging.warning(
                            f"⚠️ 生成的岗位族谱覆盖不足(仅 {total_lvl2} 个二级岗位，要求至少 50 个)，"
                            f"将进行第 {attempt + 1} 次尝试..."
                        )
                        time.sleep(2)  # 短暂等待后重试
                        continue
                    else:
                        logging.error(f"❌ 生成的岗位族谱覆盖不足(仅 {total_lvl2} 个二级岗位，要求至少 50 个)")
                        raise ValueError("生成的岗位族谱覆盖不足，请重新生成。")
                
                logging.info("✅ 岗位族谱验证通过")
                return taxonomy
            except (json.JSONDecodeError, KeyError) as e:
                if attempt < max_retries:
                    logging.warning(f"⚠️ 解析 LLM 响应失败：{e}，将进行第 {attempt + 1} 次尝试...")
                    time.sleep(2)
                    continue
                else:
                    raise
        
        raise RuntimeError("多次尝试后仍无法生成合格的岗位族谱。")

    def get_candidates(
        self, job_text: str, top_level1: int = 4, max_level2: int = 40
    ) -> List[Dict[str, Any]]:
        if not self.level2_index:
            raise RuntimeError("岗位族谱尚未初始化。")

        text_norm = normalize_text(job_text)
        scored_entries: List[Tuple[float, Level2Entry]] = []
        for entry in self.level2_index:
            keywords = [normalize_text(k) for k in entry.keywords]
            hit = sum(1 for k in keywords if k and k in text_norm)
            ratio = SequenceMatcher(
                None, text_norm, normalize_text(entry.level2)
            ).ratio()
            score = ratio + hit * 0.3
            if hit:
                score += 0.5
            if score > 0.15:
                scored_entries.append((score, entry))

        if not scored_entries:
            # 兜底：返回首批分类
            fallback = self.level2_index[:max_level2]
            return self._group_by_level1(fallback, top_level1, max_level2)

        scored_entries.sort(reverse=True, key=lambda x: x[0])
        filtered_entries = [entry for _, entry in scored_entries[:max_level2]]
        return self._group_by_level1(filtered_entries, top_level1, max_level2)

    def _group_by_level1(
        self,
        entries: Sequence[Level2Entry],
        top_level1: int,
        max_level2: int,
    ) -> List[Dict[str, Any]]:
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for entry in entries:
            grouped[entry.level1].append(
                {
                    "name": entry.level2,
                    "keywords": entry.keywords,
                    "description": entry.description,
                }
            )
        sorted_level1 = list(grouped.items())[:top_level1]
        payload = []
        total = 0
        for lvl1_name, lvl2_items in sorted_level1:
            if total >= max_level2:
                break
            payload.append(
                {
                    "level1": lvl1_name,
                    "level2_options": lvl2_items[: max_level2 - total],
                }
            )
            total += len(payload[-1]["level2_options"])
        return payload


class JobAgent:
    """主流程：整合岗位文本 -> 调用 LLM -> 结果落地。"""

    def __init__(
        self,
        skill_repo: SkillRepository,
        taxonomy_manager: TaxonomyManager,
        llm_client: OpenAIClient,
        min_skill_count: int = 3,
        max_skill_count: int = 10,
    ) -> None:
        self.skill_repo = skill_repo
        self.taxonomy_manager = taxonomy_manager
        self.llm_client = llm_client
        self.min_skill_count = min_skill_count
        self.max_skill_count = max_skill_count
        self.signal_analyzer = JobSignalAnalyzer()
        self.knowledge_retriever = KnowledgeRetriever(PROGRAM_CACHE_FILE)
        self.skill_review_agent = SkillReviewAgent(llm_client)

    def process_jobs(
        self,
        jobs: List[Dict[str, Any]],
        output_path: Path,
        max_workers: int = MAX_WORKERS,
    ) -> None:
        """并行处理所有岗位"""
        total_jobs = len(jobs)
        logging.info(f"🚀 开始并行处理 {total_jobs} 个岗位，使用 {max_workers} 个并行线程...")
        
        def process_job_wrapper(args):
            """包装函数，用于并行处理单个岗位"""
            idx, job = args
            job_id = job.get("job_id") or f"JOB_{idx}"
            try:
                result = self._process_single_job(job)
                result["job_id"] = job_id
                return idx, {**job, **result}, None
            except Exception as err:
                logging.exception("岗位 %s 处理失败：%s", job_id, err)
                return idx, {**job, **self._empty_result(job_id)}, err
        
        # 准备任务列表
        tasks = [(idx, job) for idx, job in enumerate(jobs, start=1)]
        results_dict = {}
        completed_count = 0
        
        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_idx = {
                executor.submit(process_job_wrapper, task): task[0]
                for task in tasks
            }
            
            # 收集结果
            for future in as_completed(future_to_idx):
                idx, result, error = future.result()
                results_dict[idx] = result
                completed_count += 1
                
                job_id = result.get("job_id", f"JOB_{idx}")
                if error:
                    logging.error("❌ 岗位 %s 处理失败 (%s/%s)", job_id, completed_count, total_jobs)
                else:
                    logging.info("✅ 完成岗位 %s (%s/%s)", job_id, completed_count, total_jobs)
                
                # 每处理 10 个岗位输出一次进度
                if completed_count % 10 == 0:
                    logging.info(f"📊 进度：{completed_count}/{total_jobs} ({completed_count*100//total_jobs}%)")
        
        # 按原始顺序整理结果
        results = [results_dict[idx] for idx in sorted(results_dict.keys())]
        
        # 保存结果 - CSV 格式
        df = pd.DataFrame(results)
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        logging.info("💾 CSV 输出已保存到 %s，总计 %s 条岗位。", output_path, len(results))
        
        # 保存结果 - JSONL 格式（避免逗号冲突）
        jsonl_path = output_path.with_suffix('.jsonl')
        with open(jsonl_path, 'w', encoding='utf-8') as f:
            for result in results:
                json_line = json.dumps(result, ensure_ascii=False)
                f.write(json_line + '\n')
        logging.info("💾 JSONL 输出已保存到 %s，总计 %s 条岗位。", jsonl_path, len(results))

    def _process_single_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        job_title = job.get("job_title", "")
        job_desc = job.get("job_description", "")
        job_req = job.get("job_requirements", "")
        special_program = job.get("special_program", "")

        job_text = "\n".join(
            [
                f"岗位名称: {job_title}",
                f"类别: {job.get('category', '')}",
                f"地点: {job.get('location', '')}",
                f"项目: {special_program}",
                "【岗位描述】",
                job_desc,
                "【任职要求】",
                job_req,
            ]
        )

        candidate_tags = self.skill_repo.get_candidate_tags(
            job_title, f"{job_desc}\n{job_req}", special_program
        )
        taxonomy_candidates = self.taxonomy_manager.get_candidates(job_text)

        strength_info = self.signal_analyzer.analyze(job)
        program_contexts = self.knowledge_retriever.lookup_terms(
            strength_info.get("program_terms", [])
        )

        llm_response = self._call_llm(
            job,
            candidate_tags,
            taxonomy_candidates,
            strength_info,
            program_contexts,
        )
        parsed = self._parse_llm_output(llm_response)
        validated = self._validate_and_normalize(parsed, job_text)

        skills = self._select_skills(
            validated.get("skills", []),
            candidate_tags,
            strength_info,
        )
        skills = self.skill_review_agent.review(
            job_text,
            strength_info,
            skills,
            lambda reply, allowed: parse_llm_response(reply, allowed),
        )
        skill_string = format_skill_string(skills)

        job_family = validated.get("job_family", {}) or {}

        return {
            "min_degree": validated.get("min_degree", {}).get("degree", ""),
            "degree_priority": validated.get("min_degree", {}).get("priority", ""),
            "major_requirement_text": validated.get("major_requirement", {}).get(
                "text", ""
            ),
            "major_requirement_priority": validated.get("major_requirement", {}).get(
                "priority", ""
            ),
            "skill_tags": skill_string,
            "job_level1": job_family.get("level1", ""),
            "job_level2": job_family.get("level2", ""),
            "llm_raw_json": json.dumps(parsed, ensure_ascii=False),
        }

    def _call_llm(
        self,
        job: Dict[str, Any],
        candidate_tags: List[str],
        taxonomy_candidates: List[Dict[str, Any]],
        strength_info: Dict[str, Any],
        program_contexts: Dict[str, str],
    ) -> str:
        system_prompt = (
            "你是资深的人力与技能分析专家，需生成结构化招聘情报。\n"
            "必须严格按照 JSON 输出，所有评分遵循以下规则：\n"
            f"{COMMON_SCORING_RULES_V4}"
        )
        job_info = [
            f"公司: {job.get('company_name', '')}",
            f"岗位: {job.get('job_title', '')}",
            f"岗位类型: {job.get('category', '')}",
            f"城市: {job.get('location', '')}",
            f"项目/序列: {job.get('special_program', '')}",
            f"链接: {job.get('apply_url', '')}",
            "",
            "【岗位描述】",
            job.get("job_description", ""),
            "",
            "【任职要求】",
            job.get("job_requirements", ""),
        ]
        strength_section = self._build_strength_prompt(strength_info)
        knowledge_section = self._build_program_context_prompt(program_contexts)
        candidate_section = (
            "【候选技能标签】请仅从下列列表中挑选最契合岗位的 3-10 个技能：\n"
            f"{', '.join(candidate_tags)}"
        )
        taxonomy_section = (
            "【候选岗位族谱】务必从以下候选中选择最贴切的一级/二级岗位：\n"
            f"{json.dumps(taxonomy_candidates, ensure_ascii=False)}"
        )
        output_schema = (
            "【输出 JSON 结构】\n"
            "{\n"
            '  "min_degree": {"degree": "本科|硕士|博士|大专", "priority": "必须|优先"},\n'
            '  "major_requirement": {"text": "不超过120字", "priority": "必须|优先"},\n'
            '  "skills": [{"name": "技能名", "score": 1-5}, ...],\n'
            '  "job_family": {"level1": "一级分类", "level2": "二级分类"}\n'
            "}\n"
            "禁止输出除 JSON 外的任何内容。"
        )
        user_prompt = "\n".join(
            job_info
            + [
                "",
                strength_section,
                "",
                knowledge_section,
                "",
                candidate_section,
                "",
                taxonomy_section,
                "",
                output_schema,
            ]
        )
        return self.llm_client.chat(
            system_prompt,
            user_prompt,
            response_format={"type": "json_object"},
        )

    def _build_strength_prompt(self, strength_info: Dict[str, Any]) -> str:
        base_score = strength_info.get("base_score", 3)
        description = strength_info.get("level_description", "常规岗位")
        signals: List[Signal] = strength_info.get("signals", [])
        lines = [
            "### 岗位强度评估",
            f"- 等级：{description}",
            f"- 核心技能评分基准：至少 {base_score} 分（如信号充足可达 4-5 分）。",
        ]
        if signals:
            lines.append("- 触发信号：")
            for sig in signals:
                lines.append(f"  * {sig.label}：{sig.impact}")
        else:
            lines.append("- 触发信号：无明显高强度信号。")
        lines.append("请依据上述信号调整技能评分，并在需要时引用原因。")
        return "\n".join(lines)

    def _build_program_context_prompt(self, program_contexts: Dict[str, str]) -> str:
        if not program_contexts:
            return "### 外部检索摘要\n无额外项目/计划背景信息。"
        lines = ["### 外部检索摘要"]
        for term, summary in program_contexts.items():
            lines.append(f"- {term}: {summary}")
        return "\n".join(lines)

    def _parse_llm_output(self, response: str) -> Dict[str, Any]:
        try:
            return json.loads(response)
        except json.JSONDecodeError as err:
            logging.error("LLM 输出无法解析为 JSON：%s", err)
            raise

    def _validate_and_normalize(
        self, payload: Dict[str, Any], job_text: str
    ) -> Dict[str, Any]:
        min_degree = payload.get("min_degree") or {}
        degree_value = self._normalize_degree(min_degree.get("degree"), job_text)
        degree_priority = self._normalize_priority(min_degree.get("priority"))

        major_req = payload.get("major_requirement") or {}
        major_priority = self._normalize_priority(major_req.get("priority"))
        major_text = str(major_req.get("text") or "").strip()
        if len(major_text) > 120:
            major_text = major_text[:117] + "..."

        job_family = payload.get("job_family") or {}
        lvl1 = job_family.get("level1") or ""
        lvl2 = job_family.get("level2") or ""

        return {
            "min_degree": {"degree": degree_value, "priority": degree_priority},
            "major_requirement": {"text": major_text, "priority": major_priority},
            "skills": payload.get("skills", []),
            "job_family": {"level1": lvl1, "level2": lvl2},
        }

    def _select_skills(
        self,
        skills_payload: List[Dict[str, Any]],
        candidate_tags: List[str],
        strength_info: Dict[str, Any],
    ) -> List[Tuple[str, int]]:
        valid_skills: List[Tuple[str, int]] = []
        for item in skills_payload:
            name = str(item.get("name") or "").strip()
            score = item.get("score")
            if not name or not isinstance(score, (int, float)):
                continue
            score_int = max(1, min(5, int(round(score))))
            if self.skill_repo.validate_skill(name):
                valid_skills.append((name, score_int))

        valid_skills = SkillNormalizer.normalize(valid_skills, candidate_tags)

        if len(valid_skills) < self.min_skill_count:
            logging.warning(
                "技能数量不足（%s），将使用候选列表兜底。",
                len(valid_skills),
            )
            fallback_needed = self.min_skill_count - len(valid_skills)
            fallback_score = max(3, strength_info.get("base_score", 3))
            for tag in candidate_tags:
                if len(valid_skills) >= self.min_skill_count:
                    break
                if any(tag == existing[0] for existing in valid_skills):
                    continue
                if tag.replace(" ", "") in LOW_INFORMATION_SKILLS:
                    continue
                if self.skill_repo.validate_skill(tag):
                    valid_skills.append((tag, fallback_score))

        if len(valid_skills) > self.max_skill_count:
            valid_skills = valid_skills[: self.max_skill_count]

        return valid_skills

    def _normalize_degree(self, value: Optional[str], job_text: str) -> str:
        if value in DEGREE_ORDER:
            return value
        fallback = self._infer_degree_from_text(job_text)
        return fallback or "本科"

    def _infer_degree_from_text(self, text: str) -> Optional[str]:
        text = text or ""
        for degree in DEGREE_ORDER:
            if degree in text:
                return degree
        return None

    def _normalize_priority(self, value: Optional[str]) -> str:
        if value in PRIORITY_VALUES:
            return value
        if not value:
            return "必须"
        value_str = str(value)
        if any(token in value_str for token in ["必", "需", "必须"]):
            return "必须"
        if any(token in value_str for token in ["优先", "加分", "佳"]):
            return "优先"
        return "必须"

    def _empty_result(self, job_id: str) -> Dict[str, Any]:
        return {
            "min_degree": "",
            "degree_priority": "",
            "major_requirement_text": "",
            "major_requirement_priority": "",
            "skill_tags": "",
            "job_level1": "",
            "job_level2": "",
            "llm_raw_json": "",
            "job_id": job_id,
        }


def load_jobs(jobs_path: Path) -> List[Dict[str, Any]]:
    if not jobs_path.exists():
        raise FileNotFoundError(f"未找到岗位 JSON：{jobs_path}")
    with open(jobs_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("岗位文件格式错误，应为数组。")
    return data


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="岗位智能结构化脚本")
    parser.add_argument("--jobs-file", type=Path, default=DEFAULT_JOBS_FILE)
    parser.add_argument("--labels-file", type=Path, default=DEFAULT_LABELS_FILE)
    parser.add_argument("--user-desc-file", type=Path, default=DEFAULT_USER_DESC_FILE)
    parser.add_argument("--taxonomy-file", type=Path, default=DEFAULT_TAXONOMY_FILE)
    parser.add_argument("--output-file", type=Path, default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--api-key-file", type=Path, default=DEFAULT_API_KEY_FILE)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--min-skills", type=int, default=3)
    parser.add_argument("--max-skills", type=int, default=10)
    parser.add_argument(
        "--max-workers",
        type=int,
        default=MAX_WORKERS,
        help=f"并行处理的最大线程数(默认: {MAX_WORKERS})",
    )
    parser.add_argument(
        "--rebuild-taxonomy",
        action="store_true",
        help="强制重新构建岗位族谱",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)

    api_keys = load_api_keys(args.api_key_file)
    api_manager = APIKeyManager(api_keys)
    llm_client = OpenAIClient(api_manager, model=args.model)

    skill_repo = SkillRepository(args.labels_file)
    taxonomy_manager = TaxonomyManager(
        args.taxonomy_file, args.user_desc_file, llm_client
    )
    taxonomy_manager.ensure_taxonomy(force_rebuild=args.rebuild_taxonomy)

    jobs = load_jobs(args.jobs_file)
    agent = JobAgent(
        skill_repo,
        taxonomy_manager,
        llm_client,
        min_skill_count=args.min_skills,
        max_skill_count=args.max_skills,
    )
    agent.process_jobs(jobs, args.output_file, max_workers=args.max_workers)


if __name__ == "__main__":
    main()

