"""Deterministic offline stand-in for LLMClient, used in demo mode.

Demo mode (FINDJOBS_DEMO=1) swaps this in for every LLM client held by the API
server, so the whole app runs without a key or network access. Responses are
canned but content-aware: they are derived from the prompts (resume text, job
title, required skills, answer length), which keeps the demo deterministic
while still reacting to what the user actually uploads or types.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s()-]{6,}\d")
_YEAR_RE = re.compile(r"(?:19|20)\d{2}")
_DEGREE_WORDS = ("PhD", "MBA", "MS", "BS", "Master", "Bachelor", "博士", "硕士", "本科")

_QUESTION_TEMPLATES = [
    "请介绍一个你实际使用{skill}完成的项目或功能，重点讲你的设计思路、遇到的最大挑战，以及最终的效果。",
    "如果让你用{skill}从零设计一个高可用的服务模块，你会怎么拆解？请结合你的经验说明关键取舍。",
    "当团队对{skill}的选型有分歧时，你会从哪些角度评估它是否合适？请结合你实际踩过的坑来说明。",
    "在{skill}方向，你最近深入解决过的一个技术问题是什么？请讲清楚问题背景、定位过程和你的方案。",
]
_DIFFICULTIES = ["medium", "hard", "medium", "easy"]


def _field(prompt: str, label: str) -> str:
    m = re.search(rf"{re.escape(label)}[:：]\s*([^\n]+)", prompt)
    return m.group(1).strip() if m else ""


def _section(text: str, start: str, ends: List[str]) -> str:
    m = re.search(rf"{start}[:：]?\s*\n?(.*?)$", text, re.IGNORECASE | re.DOTALL)
    if not m:
        return ""
    body = m.group(1)
    cut = len(body)
    for end in ends:
        em = re.search(rf"{end}[:：]", body, re.IGNORECASE)
        if em:
            cut = min(cut, em.start())
    return body[:cut]


class DemoLLM:
    """Duck-typed replacement for llm_client.LLMClient. Never touches the network."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
    ) -> str:
        kind = self._route(system_prompt, user_prompt)
        self.calls.append({"kind": kind})
        handler = getattr(self, f"_{kind}", self._generic)
        return handler(system_prompt, user_prompt)

    @staticmethod
    def _route(system_prompt: str, user_prompt: str) -> str:
        text = system_prompt + "\n" + user_prompt
        if "简历解析专家" in text:
            return "resume_info"
        if "职位画像分析专家" in text:
            return "level3"
        if "技能评估专家" in text or "待评分标签列表" in text:
            return "skill_score"
        if "career coach" in text:
            return "final_feedback"
        if "Candidate's answer:" in user_prompt:
            return "evaluate"
        if "Generate one concrete technical interview question" in text:
            return "question"
        if "transition from the introduction stage" in text:
            return "ack"
        if '"greeting"' in user_prompt:
            return "greeting"
        if "结构化招聘情报" in text:
            return "job_analysis"
        if "技能评审官" in text:
            return "review_noop"
        logging.warning(f"demo LLM: unrecognized prompt, using generic reply: {text[:80]!r}")
        return "generic"

    # ---------- resume parsing ----------

    def _resume_info(self, system_prompt: str, user_prompt: str) -> str:
        body = user_prompt.split("\n\n", 1)[1] if "\n\n" in user_prompt else user_prompt
        body = body.split("输出格式", 1)[0]

        name = _field(body, "Name") or _field(body, "姓名")
        if not name:
            for line in body.splitlines():
                if line.strip():
                    name = line.strip()
                    break

        email_m = _EMAIL_RE.search(body)
        phone_m = _PHONE_RE.search(body)

        education = []
        for line in _section(body, "Education", ["Experience", "Skills", "Projects", "Work"]).splitlines():
            line = line.strip().lstrip("-•* ")
            if not line or not re.search(r"university|college|institute|大学|学院", line, re.IGNORECASE):
                continue
            parts = [p.strip() for p in re.split(r"[|｜]", line)]
            fields = [p for seg in parts for p in seg.split("，") if p.strip()] if len(parts) == 1 else parts
            fields = [f for f in (p.strip() for p in fields) if f]
            if not fields:
                continue
            school = fields[0]
            degree, major = "", ""
            if len(fields) > 1:
                for word in _DEGREE_WORDS:
                    if word in fields[1]:
                        degree = word
                        major = fields[1].replace(word, "").strip(" ,")
                        break
                if not degree:
                    major = fields[1]
            year = ""
            if len(fields) > 2:
                years = _YEAR_RE.findall(fields[2])
                if years:
                    year = "-".join(years)
            education.append({"school": school, "degree": degree, "major": major, "year": year})

        experience = []
        exp_section = _section(body, "Experience", ["Skills", "Projects", "Education"])
        for chunk in re.split(r"\n\s*[-•*]\s*", "\n" + exp_section):
            chunk = re.sub(r"\s+", " ", chunk).strip()
            if not chunk:
                continue
            parts = [p.strip() for p in re.split(r"[|｜]", chunk)]
            if len(parts) < 2:
                continue
            duration, _, description = parts[2].partition(":") if len(parts) > 2 else ("", "", "")
            experience.append({
                "company": parts[0],
                "position": parts[1],
                "duration": duration.strip(),
                "description": description.strip(),
            })

        return json.dumps({
            "name": name,
            "email": email_m.group(0) if email_m else "",
            "phone": phone_m.group(0).strip() if phone_m else "",
            "education": education,
            "experience": experience,
        }, ensure_ascii=False)

    # ---------- resume skill scoring ----------

    def _level3(self, system_prompt: str, user_prompt: str) -> str:
        profile = user_prompt.split("### 候选人简历", 1)[-1].split("### 可选", 1)[0]
        excerpt = user_prompt.split("按语义选择即可）", 1)[-1].split("输出要求", 1)[0]
        choices = [c.strip() for c in excerpt.replace("\n", " ").split(",") if c.strip()]
        picked = [c for c in choices if c.lower() in profile.lower()][:5]
        return ", ".join(picked or choices[:3])

    def _skill_score(self, system_prompt: str, user_prompt: str) -> str:
        profile = user_prompt.split("### 任务详情", 1)[0].lower()
        # the marker appears twice in the prompt (instruction + list); take the last one
        tags_raw = user_prompt.rsplit("【待评分标签列表】", 1)[-1]
        tags_raw = re.sub(r"^[\s:：]+", "", tags_raw)
        tags = [t.strip() for t in re.split(r"[,，]", tags_raw) if t.strip()]
        pairs = []
        for tag in tags:
            mentions = profile.count(tag.lower())
            score = 4 if mentions >= 2 else 3 if mentions == 1 else 1
            pairs.append(f"{tag}:{score}")
        return " ".join(pairs)

    # ---------- interview ----------

    def _greeting(self, system_prompt: str, user_prompt: str) -> str:
        title = _field(user_prompt, "Job title")
        company = _field(user_prompt, "Company")
        if title:
            greeting = (
                f"你好，欢迎参加{company or '我们公司'}{title}岗位的模拟面试。"
                "整场面试分三个环节：先是自我介绍，然后我会围绕岗位要求问几个技术问题，最后给出总结反馈。"
            )
            self_intro = (
                "请先做一个简短的自我介绍，包括你的教育背景、工作或项目经历和核心技能，"
                f"并重点说说你为什么对{company or '我们公司'}的{title}岗位感兴趣，以及你有哪些相关经验。"
            )
        else:
            greeting = "你好，欢迎参加本次模拟面试。整场面试分三个环节：自我介绍、技术问答和总结反馈。"
            self_intro = "请先做一个简短的自我介绍，包括你的教育背景、工作或项目经历和核心技能，以及你想面试的岗位方向。"
        return json.dumps({"greeting": greeting, "self_intro": self_intro, "stage": "greeting"}, ensure_ascii=False)

    def _ack(self, system_prompt: str, user_prompt: str) -> str:
        return "谢谢你的介绍，你的背景和经历我有了大致了解。接下来进入技术问答环节，请尽量结合具体项目来回答。"

    def _question(self, system_prompt: str, user_prompt: str) -> str:
        skills_raw = _field(user_prompt, "Core required skills (from job or resume)")
        skills = [s.strip() for s in skills_raw.split(",") if s.strip() and s.strip() != "general software engineering"]
        if not skills:
            skills = ["项目经验"]
        # 只数 Previously asked questions 区块里的列表项，简历里的 "- " 行不算
        asked_block = user_prompt.split("Previously asked questions:", 1)[-1] if "Previously asked questions:" in user_prompt else ""
        asked = len(re.findall(r"^-\s", asked_block, re.MULTILINE))
        idx = asked % len(skills)
        question = _QUESTION_TEMPLATES[asked % len(_QUESTION_TEMPLATES)].format(skill=skills[idx])
        return json.dumps({
            "question": question,
            "difficulty": _DIFFICULTIES[asked % len(_DIFFICULTIES)],
            "category": "technical",
        }, ensure_ascii=False)

    def _evaluate(self, system_prompt: str, user_prompt: str) -> str:
        question = ""
        qm = re.search(r"Question:\s*\n?(.*?)\n\s*Candidate's answer:", user_prompt, re.DOTALL)
        if qm:
            question = qm.group(1).strip()
        answer = user_prompt.split("Candidate's answer:", 1)[-1].split("Please grade", 1)[0].strip()

        length = len(answer)
        score = 5 if length >= 300 else 4 if length >= 120 else 3 if length >= 40 else 2 if length >= 10 else 1
        topic = question[:30] + "..." if len(question) > 30 else question
        band = {
            5: ("回答非常完整，既有背景也有细节和结果。", ["结构清晰，有量化结果", "对难点的分析到位"], ["可以补充一下方案之外的备选思路"]),
            4: ("回答比较扎实，覆盖了问题的关键点。", ["有具体项目支撑", "能讲清楚自己的贡献"], ["细节数据可以再多一些"]),
            3: ("回答基本正确，但深度和细节还有提升空间。", ["答到了问题的要点"], ["多补充具体场景和结果数据", "展开讲讲关键技术取舍"]),
            2: ("回答偏简略，能看出了解但缺少实质内容。", ["方向基本正确"], ["结合一个完整项目来组织回答", "补充遇到的具体问题和解决过程"]),
            1: ("回答太短，几乎无法判断掌握程度。", ["态度认真"], ["建议先复盘自己的项目再练习表达", "按背景、方案、结果的结构来回答"]),
        }[score]
        return json.dumps({
            "score": score,
            "feedback": f"针对「{topic}」这一问题：{band[0]}" if topic else band[0],
            "strengths": band[1],
            "improvements": band[2],
            "needs_followup": score <= 2,
        }, ensure_ascii=False)

    def _final_feedback(self, system_prompt: str, user_prompt: str) -> str:
        avg = _field(user_prompt, "Average score").split("/")[0] or "N/A"
        title = _field(user_prompt, "Job title")
        company = _field(user_prompt, "Company")
        role = f"{company}{title}" if title else "目标岗位"
        return (
            f"面试结束，这是你的整体反馈报告：\n\n"
            f"1) 总体评价：本场面试平均得分 {avg}/5。整体来看，你具备{role}所需的基础能力，回答能够覆盖大部分问题的要点。\n\n"
            f"2) 主要优势：表达结构比较清晰，能够结合自己的项目经历来回答，对核心技能有实际的使用经验。\n\n"
            f"3) 待提升点：部分回答缺少量化结果和深度细节，建议按背景、方案、结果的结构组织回答，多准备可以验证的数据。\n\n"
            f"4) 岗位技能画像：建议对照岗位要求逐项自查，把回答中暴露的薄弱技能优先补齐，并准备一两个能体现深度的项目故事。\n\n"
            f"5) 学习建议：针对本次得分较低的问题重做梳理，形成文字稿后再做一次模拟面试，检验改进效果。"
        )

    # ---------- job structuring (job_agent) ----------

    def _job_analysis(self, system_prompt: str, user_prompt: str) -> str:
        # candidate tags sit on the line right after the 候选技能标签 header
        raw_tags: List[str] = []
        if "【候选技能标签】" in user_prompt:
            tag_area = user_prompt.split("【候选技能标签】", 1)[1]
            tag_area = tag_area.split("\n", 1)[-1] if "\n" in tag_area else ""
            tag_area = tag_area.split("【", 1)[0]
            raw_tags = [t.strip() for t in re.split(r"[,，]", tag_area) if t.strip()]
        try:
            from .job_agent import LOW_INFORMATION_SKILLS
        except Exception:
            LOW_INFORMATION_SKILLS = {"AI", "人工智能", "技术", "数学", "计算机", "科研", "能力", "技能"}
        tags = [t for t in raw_tags if t.replace(" ", "") not in LOW_INFORMATION_SKILLS]
        picked = tags[:6] or raw_tags[:3]
        score_seq = [5, 5, 4, 4, 4, 3]
        skills = [{"name": t, "score": score_seq[i]} for i, t in enumerate(picked)]

        level1, level2 = "", ""
        if "【候选岗位族谱】" in user_prompt:
            tax_area = user_prompt.split("【候选岗位族谱】", 1)[1]
            tax_area = tax_area.split("\n", 1)[-1] if "\n" in tax_area else ""
            tax_area = tax_area.split("【输出 JSON 结构】", 1)[0].strip()
            try:
                tax = json.loads(tax_area)
                if tax:
                    level1 = tax[0].get("level1", "")
                    options = tax[0].get("level2_options") or []
                    if options:
                        level2 = options[0].get("name", "")
            except Exception:
                pass

        degree = "本科"
        job_block = user_prompt.split("### 岗位强度评估", 1)[0]
        for d in ("博士", "硕士"):
            if d in job_block:
                degree = d
                break

        return json.dumps({
            "min_degree": {"degree": degree, "priority": "必须"},
            "major_requirement": {"text": "计算机、软件工程、人工智能、数学等相关专业", "priority": "优先"},
            "skills": skills,
            "job_family": {"level1": level1, "level2": level2},
        }, ensure_ascii=False)

    def _review_noop(self, system_prompt: str, user_prompt: str) -> str:
        # empty reply = 无需调整，parse_llm_response 返回空，保持原评分
        return ""

    def _generic(self, system_prompt: str, user_prompt: str) -> str:
        return "收到，我们继续。"
