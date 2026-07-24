"""Tests for InterviewAgent's deterministic helpers and stub-LLM flows."""

from __future__ import annotations

import json

from interview_agent import InterviewAgent


def _agent() -> InterviewAgent:
    return InterviewAgent()


class _StubLLM:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = []

    def chat(self, system_prompt, user_prompt, response_format=None, temperature=None):
        self.calls.append({"system": system_prompt, "user": user_prompt, "format": response_format})
        return json.dumps(self.payload)


# ------------------------------------------------------------------
# _extract_json_from_text
# ------------------------------------------------------------------

def test_extract_json_from_fenced_block():
    text = 'Sure, here you go:\n```json\n{"score": 4, "feedback": "good"}\n```\nDone.'
    assert _agent()._extract_json_from_text(text) == {"score": 4, "feedback": "good"}


def test_extract_json_from_raw_embedded_object():
    text = 'The result is {"a": 1, "b": [1, 2]} as shown.'
    assert _agent()._extract_json_from_text(text) == {"a": 1, "b": [1, 2]}


def test_extract_json_returns_none_on_garbage():
    assert _agent()._extract_json_from_text("no json here at all") is None


def test_extract_json_malformed_fence_returns_none():
    assert _agent()._extract_json_from_text('```json\n{broken: true,}\n```') is None


# ------------------------------------------------------------------
# _build_resume_context
# ------------------------------------------------------------------

def test_resume_context_empty():
    assert _agent()._build_resume_context(None) == "No resume information"


def test_resume_context_full():
    resume = {
        "extracted_info": {
            "name": "Ada",
            "education": [{"school": "HKU", "degree": "MS", "major": "CS", "year": "2026"}],
            "experience": [{"company": "Moonshot", "position": "Engineer", "duration": "2y"}],
        },
        "skills": [{"skill_name": "Python", "score": 5}],
    }
    context = _agent()._build_resume_context(resume)
    assert "Name: Ada" in context
    assert "HKU MS CS (2026)" in context
    assert "Moonshot Engineer (2y)" in context
    assert "Python (score: 5/5)" in context


def test_resume_context_skills_only():
    context = _agent()._build_resume_context({"skills": [{"skill_name": "Go", "score": 3}]})
    assert "Go (score: 3/5)" in context
    assert "Name:" not in context


# ------------------------------------------------------------------
# _build_job_context
# ------------------------------------------------------------------

def test_job_context_empty():
    assert _agent()._build_job_context(None) == "No specific job information"


def test_job_context_full():
    job = {
        "title": "LLM Engineer",
        "company": "ByteDance",
        "description": "Build agents",
        "required_skills": ["Python", "RAG"],
    }
    context = _agent()._build_job_context(job)
    assert "Job title: LLM Engineer" in context
    assert "Company: ByteDance" in context
    assert "Required skills: Python, RAG" in context


# ------------------------------------------------------------------
# evaluate_answer with a stub LLM
# ------------------------------------------------------------------

def test_evaluate_answer_parses_stub_llm_payload():
    agent = _agent()
    agent.llm = _StubLLM(
        {"score": 4, "feedback": "扎实", "strengths": ["有经验"], "improvements": ["细节"], "needs_followup": True}
    )

    result = agent.evaluate_answer("讲讲你的项目", "我做过 RAG 系统", None, None)

    assert result is not None
    assert result.score == 4
    assert result.feedback == "扎实"
    assert result.strengths == ["有经验"]
    assert result.needs_followup is True
    assert agent.llm.calls, "the stub LLM should have been called once"


def test_evaluate_answer_defaults_on_partial_payload():
    agent = _agent()
    agent.llm = _StubLLM({"score": 2})

    result = agent.evaluate_answer("q", "a", None, None)

    assert result is not None
    assert result.score == 2
    assert result.strengths == []
    assert result.needs_followup is False


def test_evaluate_answer_returns_none_on_unparseable_llm_output():
    class _GarbageLLM:
        def chat(self, *args, **kwargs):
            return "not json at all"

    agent = _agent()
    agent.llm = _GarbageLLM()

    assert agent.evaluate_answer("q", "a", None, None) is None
