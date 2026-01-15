#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""智能AI面试官 - 支持自适应问题生成与智能追问"""
from __future__ import annotations

import json
import logging
import os
import random
import sys
import time
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from openai import OpenAI

from llm_utils import apply_temperature_strategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_API_KEY_FILE = ROOT_DIR / "API_key-openai.md"


def load_api_keys(file_path: Path = DEFAULT_API_KEY_FILE) -> List[str]:
    """从 API_key-openai.md 文件加载所有API key"""
    if not file_path.exists():
        raise FileNotFoundError(f"未找到 API key 文件: {file_path}")
    api_keys: List[str] = []
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
    logging.info(f"成功加载 {len(api_keys)} 个API key")
    return api_keys


# 加载所有API key
API_KEYS = load_api_keys()

MODEL = os.getenv('MODEL', 'gpt-5-mini')
TIMEOUT_S = 180
MAX_RETRY = 3
TEMPERATURE = 0.7

# API key轮询锁
_api_key_lock = Lock()
_api_key_index = 0

@dataclass
class SubjectiveQuestion:
    question: str
    grading_rubric: str
    difficulty: str = "medium"  # easy, medium, hard
    reference_answer: Optional[str] = None
    thinking_guide: Optional[str] = None

@dataclass
class GradedAnswer:
    score: int
    reason: str
    strengths: List[str]
    flaws: List[str]
    needs_followup: bool = False  # 是否需要追问

@dataclass
class InterviewSession:
    question: SubjectiveQuestion
    user_answer: str
    grading_result: GradedAnswer
    followup_question: Optional[str] = None

def get_next_api_key() -> str:
    """轮询获取下一个API key"""
    global _api_key_index
    with _api_key_lock:
        key = API_KEYS[_api_key_index % len(API_KEYS)]
        _api_key_index += 1
        return key

class LLMClient:
    def __init__(self, api_key: str = None, model: str = None, timeout: int = None, max_retry: int = None):
        self.api_key = api_key or get_next_api_key()
        self.model = model or MODEL
        self.timeout = timeout or TIMEOUT_S
        self.max_retry = max_retry or MAX_RETRY
        self.client = OpenAI(api_key=self.api_key)

    def _make_request(self, messages: List[Dict], temperature: float, is_json: bool = False) -> Optional[Dict[str, Any]]:
        last_err = None
        prepared_messages = list(messages)
        base_system_prompt = ""
        if prepared_messages and prepared_messages[0].get("role") == "system":
            base_system_prompt = prepared_messages[0].get("content", "")
        adjusted_prompt, temp_param = apply_temperature_strategy(
            self.model, base_system_prompt, temperature
        )
        if prepared_messages and prepared_messages[0].get("role") == "system":
            prepared_messages[0] = {**prepared_messages[0], "content": adjusted_prompt}
        else:
            prepared_messages.insert(0, {"role": "system", "content": adjusted_prompt})
        
        for attempt in range(1, self.max_retry + 1):
            try:
                logging.info(f"LLM请求中 (第{attempt}/{self.max_retry}次)...")
                kwargs = {
                    "model": self.model,
                    "messages": prepared_messages,
                    "timeout": self.timeout,
                }
                if temp_param is not None:
                    kwargs["temperature"] = temp_param
                if is_json:
                    kwargs["response_format"] = {"type": "json_object"}
                
                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                if not content:
                    raise ValueError('LLM响应内容为空')
                return json.loads(content) if is_json else {"content": content}
            except Exception as e:
                last_err = e
                wait = (2 ** attempt) + random.uniform(0, 1)
                logging.warning(f"LLM请求失败: {e}，{wait:.1f}s后重试...")
                if attempt < self.max_retry:
                    time.sleep(wait)
        logging.error(f"LLM多次请求失败: {last_err}")
        return None

    def generate_text(self, system_prompt: str, user_prompt: str, temperature: float = TEMPERATURE) -> Optional[str]:
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        response = self._make_request(messages, temperature, is_json=False)
        return response.get("content") if response else None

    def generate_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> Optional[Dict[str, Any]]:
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        return self._make_request(messages, temperature, is_json=True)

class InterviewModule:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate_questions(self, level_3rd: str, skill_type: str, tag: str, 
                          num_questions: int = 3, history: List[InterviewSession] = None,
                          avg_score: float = 0.0) -> Optional[List[SubjectiveQuestion]]:
        """根据技能标签和面试历史动态生成主观题"""
        # 根据平均分调整难度
        if avg_score >= 4.0:
            difficulty_hint = "生成较难的问题，考察深度思考能力"
        elif avg_score >= 2.5:
            difficulty_hint = "生成中等难度的问题"
        else:
            difficulty_hint = "生成基础但重要的问题，帮助建立信心"
        
        history_context = ""
        if history:
            history_context = "\n\n面试历史（用于调整问题难度和方向）：\n"
            for i, session in enumerate(history[-3:], 1):  # 只考虑最近3题
                history_context += f"问题{i}: {session.question.question[:50]}...\n"
                history_context += f"得分: {session.grading_result.score}/5\n"

        system_prompt = f"""
role: adaptive_quiz_designer_v5
language: zh-CN
output_format: STRICT_JSON_ONLY

contract:
type: object
required: [questions]
properties:
    questions:
    type: array
    minItems: {num_questions}
    maxItems: {num_questions}
    items:
        type: object
        required: [question_type, question, difficulty, reference_answer, thinking_guide, grading_rubric]
        properties:
        question_type: {{type: string, enum: ["subjective"]}}
        question: {{type: string, minLength: 15}}
        difficulty: {{type: string, enum: ["easy", "medium", "hard"]}}
        reference_answer: {{type: string, minLength: 20}}
        thinking_guide: {{type: string, minLength: 15}}
        grading_rubric: {{type: string, minLength: 50}}

rubric_requirements:
- 主观题必须包含字段 grading_rubric，且是详尽的评分细则，面向 0-5 分逐级打分。
- 评分维度（至少 5 项）：问题理解、逻辑结构、方案可行性、细节深度、沟通表达等。
- 为 0/1/2/3/4/5 每一分级提供"可观察行为锚点"，描述清晰可操作。
- 必须指出"一票否决/直接判0分"的边界（如违规、编造数据等）。

constraints:
- 仅返回一个 JSON 对象，不要 markdown 代码围栏或额外说明。
- 全中文，且不含不当内容。
"""
        user_prompt = f"""
请严格按照契约，为以下技能生成 {num_questions} 道高质量的主观面试题：
- 职业领域(level_3rd): {level_3rd}
- 技能类型(skill_type): {skill_type}
- 核心技能(tag): {tag}
- 难度要求: {difficulty_hint}
{history_context}
确保每道题都包含详尽的 `grading_rubric` 和 `difficulty` 字段。
"""
        logging.info("正在生成面试题目...")
        response = self.llm.generate_json(system_prompt, user_prompt)
        if response and "questions" in response:
            try:
                questions = [
                    SubjectiveQuestion(
                        question=q['question'],
                        grading_rubric=q['grading_rubric'],
                        difficulty=q.get('difficulty', 'medium'),
                        reference_answer=q.get('reference_answer'),
                        thinking_guide=q.get('thinking_guide')
                    ) for q in response['questions']
                ]
                logging.info(f"成功生成 {len(questions)} 道题目。")
                return questions
            except (KeyError, TypeError) as e:
                logging.error(f"解析题目JSON失败: {e}")
                return None
        return None

    def grade_answer(self, question: SubjectiveQuestion, user_answer: str) -> Optional[GradedAnswer]:
        system_prompt = """
你是专业、严格且公平的AI面试官。根据[评分标准]对[作答内容]进行评估。

严格要求：
- 必须找出关键缺陷和优点
- 不要因为"努力"而给高分，要看实际产出
- 空泛表述直接降分，缺乏具体性严重扣分
- 逻辑错误是重大扣分项

输出JSON格式：
{
"score": <0-5整数>,
"reason": "<详细分析，结合评分标准，指出具体问题和亮点>",
"strengths": ["<优点1>", "<优点2>"],
"flaws": ["<缺陷1>", "<缺陷2>"],
"needs_followup": <true/false>,
"followup_reason": "<如果需要追问，说明原因>"
}

追问规则：
- 如果得分<=2分且回答有明显缺陷，建议追问
- 如果回答过于简短或模糊，建议追问
- 如果回答有亮点但不够深入，建议追问以挖掘潜力
"""
        user_prompt = f"""
[问题]: {question.question}
[评分标准]: {question.grading_rubric}
[待评答案]: {user_answer}

请严格按照评分标准和输出格式，返回JSON评分结果。
"""
        logging.info("正在对回答进行评分...")
        response = self.llm.generate_json(system_prompt, user_prompt)
        if response:
            try:
                return GradedAnswer(
                    score=int(response['score']),
                    reason=response['reason'],
                    strengths=response.get('strengths', []),
                    flaws=response.get('flaws', []),
                    needs_followup=response.get('needs_followup', False)
                )
            except (KeyError, ValueError, TypeError) as e:
                logging.error(f"解析评分JSON失败: {e}")
                return None
        return None

    def generate_followup(self, question: SubjectiveQuestion, user_answer: str, 
                         grading_result: GradedAnswer) -> Optional[str]:
        """根据回答和评分生成智能追问"""
        if not grading_result.needs_followup:
            return None
        
        system_prompt = "你是专业的AI面试官，擅长通过追问深入挖掘面试者的能力。"
        user_prompt = f"""
原问题: {question.question}
面试者回答: {user_answer}
评分: {grading_result.score}/5
主要缺陷: {', '.join(grading_result.flaws) if grading_result.flaws else '无'}

请生成一个简洁、有针对性的追问（30字以内），帮助面试者更好地展示能力或澄清模糊点。
追问应该：
1. 针对回答中的关键缺陷或模糊点
2. 语气友好，引导性而非质疑性
3. 帮助面试者补充或深化回答

只返回追问内容，不要其他说明。
"""
        return self.llm.generate_text(system_prompt, user_prompt, temperature=0.7)

class InterviewOrchestrator:
    def __init__(self):
        self.llm_client = LLMClient()  # 使用轮询的API key
        self.module = InterviewModule(self.llm_client)
        self.interview_history: List[InterviewSession] = []
        self.level_3rd = ""
        self.skill_type = ""
        self.tag = ""

    def _get_multiline_input(self) -> str:
        print("请输入你的回答 (输入 'END' 并回车结束):")
        lines = []
        while True:
            line = input()
            if line.strip().upper() == 'END':
                break
            lines.append(line)
        return "\n".join(lines)

    def _calculate_avg_score(self) -> float:
        """计算当前平均分"""
        valid_scores = [s.grading_result.score for s in self.interview_history if s.grading_result.score >= 0]
        return sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

    def _determine_question_count(self, initial_count: int = 3) -> int:
        """根据表现动态决定问题数量"""
        if len(self.interview_history) == 0:
            return initial_count
        
        avg_score = self._calculate_avg_score()
        # 表现优秀时增加难度和题量，表现不佳时减少题量但保持基础考察
        if avg_score >= 4.0:
            return min(initial_count + 1, 5)  # 最多5题
        elif avg_score <= 2.0:
            return max(initial_count - 1, 2)  # 至少2题
        return initial_count

    def run(self):
        print("="*50)
        print("欢迎来到智能AI面试系统！")
        print("="*50)
        self.level_3rd = input("请输入面试的职业领域 (例如: '产品经理'): ")
        self.skill_type = input("请输入面试的技能类型 (例如: '产品设计'): ")
        self.tag = input("请输入面试的核心技能 (例如: '用户体验'): ")
        print("-" * 50)

        logging.info("正在生成面试开场白...")
        opening_statement = self.llm_client.generate_text(
            system_prompt="你是一位友好、专业的AI面试官。",
            user_prompt=f"为一场关于'{self.level_3rd}'岗位的'{self.tag}'技能的面试，生成一段简短（100字以内）、亲切的开场白，让面试者放松下来。"
        )
        print(f"\nAI面试官: {opening_statement or '你好，很高兴能和你进行这次面试。我们开始吧。'}\n")
        time.sleep(1)

        # 智能问题生成：初始3题，后续根据表现动态调整
        initial_questions = self.module.generate_questions(
            self.level_3rd, self.skill_type, self.tag, 
            num_questions=3, history=None, avg_score=0.0
        )
        if not initial_questions:
            print("抱歉，无法生成面试题，请检查输入或网络后重试。")
            return

        question_queue = list(initial_questions)
        question_index = 0

        while question_index < len(question_queue):
            q = question_queue[question_index]
            print(f"--- 问题 {question_index + 1} ---\n")
            print(f"[难度: {q.difficulty.upper()}] {q.question}")
            print("-" * 20)
            
            user_answer = self._get_multiline_input()
            if not user_answer.strip():
                user_answer = "（用户未回答）"

            grading_result = self.module.grade_answer(q, user_answer)
            followup_question = None

            if grading_result:
                print("\n--- AI评分与反馈 ---")
                print(f"本题得分: {grading_result.score} / 5")
                print(f"简要评价: {grading_result.reason}")
                
                # 智能追问
                if grading_result.needs_followup:
                    followup_question = self.module.generate_followup(q, user_answer, grading_result)
                    if followup_question:
                        print(f"\n💡 追问: {followup_question}")
                        print("-" * 20)
                        followup_answer = self._get_multiline_input()
                        if followup_answer.strip():
                            # 对追问回答进行简单评分（可选）
                            print("\n感谢你的补充回答。\n")
                
                print("-" * 50 + "\n")
                self.interview_history.append(InterviewSession(q, user_answer, grading_result, followup_question))
            else:
                print("\n抱歉，评分失败，我们继续下一题。\n")
                failed_grade = GradedAnswer(-1, "评分失败", [], [])
                self.interview_history.append(InterviewSession(q, user_answer, failed_grade))

            question_index += 1
            
            # 动态生成后续问题
            if question_index >= len(question_queue) and question_index < 5:
                avg_score = self._calculate_avg_score()
                next_count = self._determine_question_count(initial_count=2)
                
                if next_count > 0:
                    logging.info(f"根据当前表现(平均分: {avg_score:.2f})，生成后续问题...")
                    next_questions = self.module.generate_questions(
                        self.level_3rd, self.skill_type, self.tag,
                        num_questions=next_count, 
                        history=self.interview_history,
                        avg_score=avg_score
                    )
                    if next_questions:
                        question_queue.extend(next_questions)

            time.sleep(1)

        if not self.interview_history:
            print("没有有效的面试记录，无法生成总结。")
            return

        logging.info("正在生成最终总结报告...")
        summary_prompt_context = "以下是一次面试的完整记录：\n\n"
        total_score = 0
        valid_grades = 0
        score_trend = []
        
        for i, session in enumerate(self.interview_history):
            summary_prompt_context += f"问题 {i + 1} [难度: {session.question.difficulty}]: {session.question.question}\n"
            summary_prompt_context += f"应聘者回答: {session.user_answer}\n"
            summary_prompt_context += f"AI评分: {session.grading_result.score}/5\n"
            summary_prompt_context += f"优点: {', '.join(session.grading_result.strengths) if session.grading_result.strengths else '无'}\n"
            summary_prompt_context += f"缺陷: {', '.join(session.grading_result.flaws) if session.grading_result.flaws else '无'}\n"
            if session.followup_question:
                summary_prompt_context += f"追问: {session.followup_question}\n"
            summary_prompt_context += "\n"
            
            if session.grading_result.score != -1:
                total_score += session.grading_result.score
                valid_grades += 1
                score_trend.append(session.grading_result.score)
        
        avg_score = (total_score / valid_grades) if valid_grades > 0 else 0
        trend_analysis = ""
        if len(score_trend) >= 2:
            if score_trend[-1] > score_trend[0]:
                trend_analysis = "表现呈上升趋势"
            elif score_trend[-1] < score_trend[0]:
                trend_analysis = "表现需要关注"
            else:
                trend_analysis = "表现稳定"

        summary_user_prompt = f"""
{summary_prompt_context}
---
任务:
请根据以上完整的面试记录，为面试者生成一份全面的总结报告。报告应包括：
1. **总体评价**: 对面试者的整体表现给出一个综合性的评价（约100-150字），注意{trend_analysis}。
2. **亮点分析**: 具体指出1-2个表现最出色的地方，结合具体问题说明。
3. **改进建议**: 针对性地提出1-2个最需要改进的地方，并给出具体、可操作的建议。
4. **能力画像**: 简要总结面试者在{self.tag}技能方面的能力水平。
5. **学习建议**: 基于本次面试表现，给出1-2条针对性的学习或练习建议。

请以友好、鼓励但专业的口吻撰写，确保建议具体可执行。
"""
        final_summary = self.llm_client.generate_text(
            system_prompt="你是资深的HR专家和职业顾问，正在为面试者撰写一份富有建设性的面试反馈报告。",
            user_prompt=summary_user_prompt,
            temperature=0.6
        )

        print("=" * 50)
        print("面试结束 - 综合反馈报告")
        print("=" * 50)
        print(f"最终平均得分: {avg_score:.2f} / 5.00")
        if trend_analysis:
            print(f"表现趋势: {trend_analysis}")
        print("\n" + "=" * 50 + "\n")
        print(final_summary or "感谢你的参与，希望这次面试能对你有所帮助！")
        print("\n" + "=" * 50)

if __name__ == '__main__':
    try:
        orchestrator = InterviewOrchestrator()
        orchestrator.run()
    except KeyboardInterrupt:
        print("\n\n面试已中断。下次再见！")
    except Exception as e:
        logging.critical(f"程序发生严重错误: {e}", exc_info=True)
