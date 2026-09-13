#!/usr/bin/env python3
"""Offline full-journey demo (no API key, no network): crawl → LLM analysis →
skill gaps → mock interview → feedback report.

Run:  python examples/full_journey_demo.py

Every LLM call is swapped for the deterministic DemoLLM, so the recording is
byte-stable; the pipeline state goes to a temp dir, not the repo data files.
"""

import csv
import json
import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from findjobs.pipeline import print_banner as banner


# ---- patch every LLM with the deterministic demo stand-in -------------------
from findjobs import job_agent, llm_client as llm_client_mod, pipeline
from findjobs.demo_llm import DemoLLM

_demo = DemoLLM()
job_agent.OpenAIClient = lambda *a, **k: _demo
llm_client_mod.LLMClient = lambda *a, **k: _demo

from findjobs.interview_agent import InterviewAgent
from findjobs.job_matcher import JobMatcher
from findjobs.job_source import JsonFileSource
from findjobs.resume_parser import ResumeParser

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_JOBS = ROOT / "data" / "sample_jobs.json"
SAMPLE_RESUME = ROOT / "data" / "sample_resume.pdf"


class _DropTagRateNoise(logging.Filter):
    # tag_rate 对罐头评分串的格式告警，演示里是已知噪声
    def filter(self, record: logging.LogRecord) -> bool:
        return "非标准字符" not in record.getMessage()


def _compact_tags(skill_str: str, limit: int = 5) -> str:
    pairs = JobMatcher().parse_job_skills(skill_str or "")
    return " · ".join(f"{name}({score})" for name, score in pairs[:limit])


def run() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
    logging.getLogger().addFilter(_DropTagRateNoise())

    workdir = Path(tempfile.mkdtemp(prefix="findjobs-demo-"))
    pipeline.ROOT_DIR = workdir  # keep the repo's data files untouched

    banner("步骤 1/4 · 爬取岗位（json-file 数据源）")
    r1 = pipeline.step1_crawl_jobs(sources=[JsonFileSource(SAMPLE_JOBS)])
    jobs = json.loads((workdir / "crawled_jobs_raw.json").read_text(encoding="utf-8"))
    print(f"入库 {r1['count']} 个岗位 · 例：{jobs[0]['job_title']} @ {jobs[0].get('company_name', '?')}")

    banner("步骤 2/4 · LLM 智能分析（学历 / 技能评分 / 岗位分类）")
    # 与 pipeline step2 同一条 job_agent 流程，只是在本进程里驱动（离线演示
    # 不起子进程），LLM 已在上文整体替换为确定性 DemoLLM。
    skill_repo = job_agent.SkillRepository(ROOT / "data" / "all_labels.csv")
    taxonomy = job_agent.TaxonomyManager(
        ROOT / "data" / "tech_taxonomy.json", Path("user_descriptions.csv"), _demo
    )
    taxonomy.ensure_taxonomy()
    agent = job_agent.JobAgent(skill_repo, taxonomy, _demo, min_skill_count=3, max_skill_count=10)
    enriched_file = workdir / "jobs_enriched.csv"
    agent.process_jobs(jobs[:3], enriched_file, max_workers=3)

    # 注意 utf-8-sig：job_agent 落盘带 BOM，读漏了会把首列名吃掉
    with open(enriched_file, encoding="utf-8-sig") as f:
        enriched = list(csv.DictReader(f))
    job0 = enriched[0]
    print(
        f"分析 {len(enriched)} 个岗位 · 例：{job0.get('job_title')} @ {job0.get('company_name')}\n"
        f"  学历要求：{job0.get('min_degree')}（{job0.get('degree_priority')}）"
        f" · 岗位族：{job0.get('job_level1')}/{job0.get('job_level2')}\n"
        f"  技能标签：{_compact_tags(job0.get('skill_tags', ''))}"
    )

    banner("步骤 3/4 · 简历 × 岗位 技能缺口")
    resume_data = ResumeParser().parse_resume(str(SAMPLE_RESUME))
    resume_skills = resume_data.get("skills") or []
    print(f"简历解析完成：{len(resume_skills)} 个技能标签已评分")
    matcher = JobMatcher()
    # match_jobs 以 API 层的岗位字典为输入：id + skill_tags_raw（name , score , AI | ...）
    matcher_jobs = [
        {**row, "id": row.get("job_id", ""), "skill_tags_raw": row.get("skill_tags", "")}
        for row in enriched
    ]
    matches = matcher.match_jobs(resume_skills, matcher_jobs)
    gaps = matcher.top_skill_gaps(matches, limit=5)
    best = matches[0] if matches else {}
    best_job = best.get("job", {})
    print(
        f"最佳匹配：{best_job.get('job_title', '—')} @ {best_job.get('company_name', '—')} · "
        f"命中技能 {len(best.get('matched_skills', []))} 个\n"
        f"最该优先补的缺口：" + ", ".join(f"{g['skill']}({g['job_count']}个岗位）" for g in gaps[:3])
    )

    banner("步骤 4/4 · 模拟面试 → 反馈报告")
    interviewer = InterviewAgent()
    skill_names = [name for name, _ in matcher.parse_job_skills(job0.get("skill_tags", ""))]
    target = {
        "title": job0.get("job_title"),
        "company": job0.get("company_name"),
        "required_skills": skill_names,
    }
    opening = interviewer.start_interview(resume_data, target)
    print(opening.get("greeting", ""))
    print(f"自我介绍题：{opening.get('self_intro', '')[:100]}…")

    question = interviewer.generate_technical_question([], resume_data, target, [])
    q_text = question.question if question else "(无题)"
    print(f"\n技术问题[{question.difficulty if question else '-'}]：{q_text}")

    answer = (
        "在之前的一个电商推荐项目里，我负责召回侧的协同过滤改造。最初是经典 item-CF，"
        "按共现次数算相似度，结果是头部商品被过度推荐、长尾商品几乎没有曝光。我把相似度改成"
        "带点击份额归一化的版本，并引入时间衰减让近期行为权重更高；同时把 item-CF 和基于类目"
        "与 Embedding 的向量召回按 7:3 做混合召回。最大的挑战是在线侧要在 50ms 内完成多路召回合并，"
        "我把相似度矩阵离线预计算后写进 Redis，在线只做查表和加权融合。中间还踩过一个坑："
        "相似度矩阵按天全量重算太贵，后来拆成增量更新，只重算当天有新行为的商品对，计算量降了约 70%。"
        "上线后长尾商品曝光占比从 8% 升到 19%，点击率提升 11%，GMV 提升 6%，"
        "这套方案也沉淀成了团队后续的召回框架。"
    )
    print(f"候选人答：{answer}")
    evaluation = interviewer.evaluate_answer(q_text, answer, resume_data, target)
    if evaluation:
        print(f"评分 {evaluation.score}/5：{evaluation.feedback}")

    conversation = [
        {"role": "assistant", "content": q_text, "question": q_text},
        {
            "role": "user",
            "content": answer,
            "evaluation": {
                "score": evaluation.score if evaluation else None,
                "feedback": evaluation.feedback if evaluation else "",
            },
        },
    ]
    feedback = interviewer.generate_final_feedback(conversation, resume_data, target)
    banner("面试反馈报告")
    print(feedback.get("final_feedback") or feedback.get("message", ""))
    avg = feedback.get("average_score")
    if avg is not None:
        print(f"\n本场平均得分：{avg:.2f}/5.00")
    print("\n全流程演示结束 · 全程离线运行，无需 API key")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
