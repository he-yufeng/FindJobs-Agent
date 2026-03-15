#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Intelligent interview module.
Features:
1. Generate interview questions based on resume and job information.
2. Structured interview flow: self‑introduction, technical Q&A, final feedback.
3. Score and evaluate the candidate's answers.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import re
import requests

try:
    from tag_rate import APIKeyManager, load_api_keys
except ImportError:
    logging.error("Failed to import tag_rate module")
    raise

# Configuration & unified LLM client
ROOT_DIR = __import__('pathlib').Path(__file__).resolve().parent
DEFAULT_API_KEY_FILE = ROOT_DIR / "API_key-openai.md"
from llm_client import LLMClient


@dataclass
class InterviewQuestion:
    """Interview question"""
    question: str
    difficulty: str = "medium"  # easy, medium, hard
    category: str = "technical"  # introduction, technical, experience


@dataclass
class AnswerEvaluation:
    """Answer evaluation"""
    score: int  # 0-5
    feedback: str
    strengths: List[str]
    improvements: List[str]
    needs_followup: bool = False


class InterviewAgent:
    """Intelligent interview agent"""
    
    def __init__(self):
        import os
        if DEFAULT_API_KEY_FILE.exists():
            api_keys = load_api_keys(DEFAULT_API_KEY_FILE)
            self.api_key_manager = APIKeyManager(api_keys)
        else:
            env_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY", "")
            self.api_key_manager = APIKeyManager([env_key]) if env_key else None
        self.llm = LLMClient(self.api_key_manager)
    
    def _call_llm(self, system_prompt: str, user_prompt: str, response_format: Optional[Dict[str, Any]] = None) -> str:
        """Call unified LLM client (supports OpenAI / DeepSeek)"""
        return self.llm.chat(system_prompt, user_prompt, response_format=response_format, temperature=0.7)
    
    def _extract_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from text, handling markdown code blocks."""
        # Try to extract JSON from fenced code block
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find a raw JSON object in text
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _build_resume_context(self, resume_data: Optional[Dict[str, Any]]) -> str:
        """Build a plain-text resume context for prompting."""
        if not resume_data:
            return "No resume information"
        
        context_parts = []
        extracted_info = resume_data.get('extracted_info', {})
        
        if extracted_info.get('name'):
            context_parts.append(f"Name: {extracted_info['name']}")
        
        if extracted_info.get('education'):
            context_parts.append("\nEducation:")
            for edu in extracted_info['education']:
                context_parts.append(
                    f"- {edu.get('school', '')} {edu.get('degree', '')} "
                    f"{edu.get('major', '')} ({edu.get('year', '')})"
                )
        
        if extracted_info.get('experience'):
            context_parts.append("\nExperience:")
            for exp in extracted_info['experience']:
                context_parts.append(
                    f"- {exp.get('company', '')} {exp.get('position', '')} "
                    f"({exp.get('duration', '')})"
                )
                if exp.get('description'):
                    context_parts.append(f"  {exp.get('description')}")
        
        if resume_data.get('skills'):
            context_parts.append("\nSkills:")
            for skill in resume_data['skills']:
                context_parts.append(
                    f"- {skill.get('skill_name', '')} "
                    f"(score: {skill.get('score', 0)}/5)"
                )
        
        return "\n".join(context_parts)
    
    def _build_job_context(self, job_data: Optional[Dict[str, Any]]) -> str:
        """Build a plain-text job context for prompting."""
        if not job_data:
            return "No specific job information"
        
        context_parts = []
        context_parts.append(f"Job title: {job_data.get('title', '')}")
        context_parts.append(f"Company: {job_data.get('company', '')}")
        
        if job_data.get('description'):
            context_parts.append(f"\nJob description:\n{job_data['description']}")
        
        if job_data.get('required_skills'):
            context_parts.append(f"\nRequired skills: {', '.join(job_data['required_skills'])}")
        
        return "\n".join(context_parts)
    
    def start_interview(
        self,
        resume_data: Optional[Dict[str, Any]],
        job_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Start interview: only generate opening greeting and self-intro prompt (no question yet)."""
        resume_context = self._build_resume_context(resume_data)
        job_context = self._build_job_context(job_data)
        
        has_job = bool(job_data and job_data.get('title'))

        if has_job:
            system_prompt = (
                "You are a professional, friendly, and experienced AI interviewer. "
                f"You are conducting an interview specifically for the role of '{job_data.get('title', '')}' at {job_data.get('company', 'the company')}. "
                "The interview has three stages: (1) self-introduction, (2) technical Q&A targeting this specific role, (3) summary & feedback. "
                "You MUST always respond in Chinese (中文)."
                "In this step, only produce a short opening greeting and a self‑introduction prompt. "
                "The greeting MUST mention the specific job title and company. "
                "The self-intro prompt should ask the candidate to explain why they are interested in THIS specific role."
            )
        else:
            system_prompt = (
                "You are a professional, friendly, and experienced AI interviewer. "
                "The interview has three stages: (1) self-introduction, (2) technical Q&A, (3) summary & feedback. "
                "You MUST always respond in Chinese (中文)."
                "In this step, only produce a short opening greeting and a self‑introduction prompt."
            )

        user_prompt = (
            f"Candidate resume (for your reference):\n{resume_context}\n\n"
            f"Target job information:\n{job_context}\n\n"
            "Please output:\n"
            "1. greeting: a concise English opening (2–3 sentences), welcoming the candidate"
            + (f" to interview for the {job_data.get('title', '')} position" if has_job else "") +
            " and briefly explaining the three stages.\n"
            "2. self_intro: an English prompt asking the candidate to introduce themselves (education, work experience, key skills)"
            + (f", and specifically why they are interested in this {job_data.get('title', '')} role and what relevant experience they have" if has_job else
               ", and optionally what position they want to interview for") + ".\n\n"
            "Output format (strict JSON, no extra text):\n"
            '{"greeting": "opening in Chinese", "self_intro": "self introduction prompt in Chinese", "stage": "greeting"}'
        )
        
        try:
            response = self._call_llm(system_prompt, user_prompt, response_format={"type": "json_object"})
            result = self._extract_json_from_text(response) or json.loads(response)
            return {
                "greeting": result.get("greeting", "Hello, thank you for joining this interview."),
                "question": None,
                "self_intro": result.get(
                    "self_intro",
                    "Please briefly introduce yourself: your education, work experience, key skills, "
                    "and what role you would like to interview for."
                ),
                "stage": result.get("stage", "greeting")
            }
        except Exception as e:
            logging.error(f"Failed to generate greeting: {e}")
            return {
                "greeting": "Hello, welcome to this interview.",
                "question": None,
                "self_intro": (
                    "Please briefly introduce yourself in Chinese: your education, work experience, "
                    "key skills, and what role you would like to interview for."
                ),
                "stage": "greeting"
            }
    
    def generate_technical_question(
        self,
        conversation_history: List[Dict[str, Any]],
        resume_data: Optional[Dict[str, Any]],
        job_data: Optional[Dict[str, Any]],
        asked_questions: List[str]
    ) -> Optional[InterviewQuestion]:
        """Generate a technical interview question."""
        resume_context = self._build_resume_context(resume_data)
        job_context = self._build_job_context(job_data)
        
        # Extract required skills from job or resume
        required_skills = []
        if job_data:
            required_skills = job_data.get('required_skills', [])
        elif resume_data and resume_data.get('skills'):
            # If there is no explicit job info, derive core skills from resume
            required_skills = [s.get('skill_name', '') for s in resume_data['skills'][:5]]
        
        has_job = bool(job_data and job_data.get('title'))

        if has_job:
            system_prompt = (
                "You are a professional technical interviewer. "
                f"You are interviewing a candidate specifically for the role of '{job_data.get('title', '')}' at {job_data.get('company', 'the company')}. "
                "You MUST answer strictly in Chinese (中文)."
                "Generate one concrete technical interview question that DIRECTLY tests the skills and knowledge required for THIS specific role. "
                "The question should:\n"
                f"1) be closely related to the job's required skills: {', '.join(required_skills[:5]) if required_skills else 'general skills'};\n"
                "2) test practical knowledge that would be needed on the job;\n"
                "3) require the candidate to demonstrate real project experience and reasoning ability;\n"
                "4) avoid repeating previously asked questions.\n\n"
                "Respond ONLY with strict JSON (no extra text or markdown):\n"
                "{\"question\":\"question text in Chinese\",\"difficulty\":\"easy|medium|hard\",\"category\":\"technical\"}"
            )
        else:
            system_prompt = (
                "You are a professional technical interviewer. "
                "You MUST answer strictly in Chinese (中文)."
                "Generate one concrete technical interview question for this candidate. "
                "The question should:\n"
                "1) target the core skills required for the role;\n"
                "2) be medium difficulty by default;\n"
                "3) require the candidate to demonstrate real project experience and reasoning ability;\n"
                "4) avoid repeating previously asked questions.\n\n"
                "Respond ONLY with strict JSON (no extra text or markdown):\n"
                "{\"question\":\"question text in Chinese\",\"difficulty\":\"easy|medium|hard\",\"category\":\"technical\"}"
            )
        
        asked_text = "\nPreviously asked questions:\n" + "\n".join(f"- {q}" for q in asked_questions[-3:]) if asked_questions else ""
        
        # Recent conversation (to capture self-intro and answers)
        conv_lines: List[str] = []
        for m in conversation_history[-6:]:
            role = "Candidate" if m.get("role") == "user" else "Interviewer"
            conv_lines.append(f"{role}: {m.get('content', '').strip()}")
        conv_text = "\n".join(conv_lines) if conv_lines else "(no prior conversation)"

        user_prompt = (
            f"Candidate resume:\n{resume_context}\n\n"
            f"Target job information:\n{job_context}\n\n"
            f"Core required skills (from job or resume): {', '.join(required_skills[:5]) if required_skills else 'general software engineering'}\n"
            f"{asked_text}\n\n"
            f"Conversation so far:\n{conv_text}\n\n"
            "Now, based on BOTH the resume and what the candidate said about themselves, "
            "generate the next technical question as strict JSON."
        )
        
        try:
            # Expect strict JSON response
            response = self._call_llm(system_prompt, user_prompt, response_format={"type": "json_object"})
            # Parse JSON (robust to optional markdown code fences)
            result = self._extract_json_from_text(response) or json.loads(response)
            question_text = str(result.get("question", "")).strip()
            difficulty = str(result.get("difficulty", "medium")).strip() or "medium"
            category = str(result.get("category", "technical")).strip() or "technical"
            if not question_text:
                question_text = (
                    "Please describe a technical project you are most familiar with, "
                    "including your specific contributions, key challenges, and how you solved them."
                )
            return InterviewQuestion(
                question=question_text,
                difficulty=difficulty,
                category=category
            )
        except Exception as e:
            logging.error(f"Failed to generate technical question: {e}")
            return InterviewQuestion(
                question=(
                    "Please describe a technical project you are most familiar with, "
                    "including your specific contributions, key challenges, and how you solved them."
                ),
                difficulty="medium",
                category="technical"
            )
    
    def evaluate_answer(
        self,
        question: str,
        answer: str,
        resume_data: Optional[Dict[str, Any]],
        job_data: Optional[Dict[str, Any]]
    ) -> Optional[AnswerEvaluation]:
        """Evaluate the candidate's answer to a given question."""
        resume_context = self._build_resume_context(resume_data)
        job_context = self._build_job_context(job_data)
        
        system_prompt = (
            "You are a professional, strict but fair AI interviewer. "
            "You MUST respond strictly in Chinese (中文)."
            "Given the question, the candidate's resume, and what they said about themselves, "
            "you need to grade the answer and give concise, helpful feedback.\n\n"
            "Scoring rules (0–5):\n"
            "5: excellent, deep understanding and rich experience;\n"
            "4: good, solid understanding and relevant experience;\n"
            "3: basically correct but shallow or missing details;\n"
            "2: partially correct but with notable gaps or confusion;\n"
            "1: mostly incorrect or very superficial;\n"
            "0: completely off-topic or no answer.\n\n"
            "Output strict JSON only:\n"
            '{"score": <integer 0-5>, "feedback": "text in Chinese", "strengths": ["..."], "improvements": ["..."], "needs_followup": true/false}'
        )
        
        user_prompt = (
            f"Candidate resume:\n{resume_context}\n\n"
            f"Target job information:\n{job_context}\n\n"
            f"Question:\n{question}\n\n"
            f"Candidate's answer:\n{answer}\n\n"
            "Please grade the answer (0–5) and provide English feedback. "
            "Explain briefly why you gave this score, list 1–3 strengths and 1–3 areas for improvement. "
            "If a deeper follow‑up question would help clarify or probe more, set needs_followup=true."
        )
        
        try:
            response = self._call_llm(system_prompt, user_prompt, response_format={"type": "json_object"})
            result = self._extract_json_from_text(response) or json.loads(response)
            return AnswerEvaluation(
                score=int(result.get("score", 3)),
                feedback=result.get("feedback", ""),
                strengths=result.get("strengths", []),
                improvements=result.get("improvements", []),
                needs_followup=result.get("needs_followup", False)
            )
        except Exception as e:
            logging.error(f"Failed to evaluate answer: {e}")
        
        return None
    
    def respond(
        self,
        user_message: str,
        conversation_history: List[Dict[str, Any]],
        resume_data: Optional[Dict[str, Any]],
        job_data: Optional[Dict[str, Any]],
        session_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Three-phase interview driven by a counter:
        - greeting: self-introduction and transition, then output Question 1
        - qa: N technical questions (configurable), each with evaluation
        - summary: final summary & feedback
        """
        resume_context = self._build_resume_context(resume_data)
        job_context = self._build_job_context(job_data)
        phase = session_state.get("phase", "greeting")
        qa_count = int(session_state.get("qa_count", 0))
        max_qa = int(session_state.get("max_qa", 5))

        if phase == "greeting":
            ack_prompt_sys = (
                "You are a professional AI interviewer. "
                "You have just read the candidate's resume and their self-introduction. "
                "Now you need to transition from the introduction stage to the technical Q&A stage. "
                "Respond ONLY in Chinese. "
                "Write 1–2 friendly sentences that (1) thank the candidate for their introduction, "
                "(2) briefly acknowledge what they said (role they want / background), and "
                "(3) clearly state that you are about to ask the first technical question. "
                "Do NOT include the question itself in this response."
            )
            ack_prompt_user = (
                f"Candidate resume (for reference):\n{resume_context}\n\n"
                f"Candidate self-introduction:\n{user_message}\n\n"
                "Please output the transition message in Chinese as described."
            )
            try:
                ack = self._call_llm(ack_prompt_sys, ack_prompt_user)
            except Exception:
                ack = "Thank you for your introduction. Let's move on to the technical questions."
            ack_str = (ack or "").strip() or "Thank you for your introduction. Let's move on to the technical questions."

            asked_questions = [msg.get('question', '') for msg in conversation_history if msg.get('question')]
            q1 = self.generate_technical_question(conversation_history, resume_data, job_data, asked_questions)
            q_text = (
                q1.question
                if q1 and q1.question
                else "Please describe a technical project you are most familiar with and your specific contributions."
            )
            return {
                "message": f"{ack_str}\n\nQuestion 1:\n{q_text}",
                "phase": "qa",
                "question": q_text,
                "evaluation": None,
                "qa_count": 0
            }

        if phase == "qa":
            last_question = None
            for msg in reversed(conversation_history):
                if msg.get('role') == 'assistant' and msg.get('question'):
                    last_question = msg.get('question')
                    break
            
            evaluation = None
            if last_question:
                evaluation = self.evaluate_answer(last_question, user_message, resume_data, job_data)
                qa_count += 1
            
            # Continue asking questions or move to summary
            asked_questions = [msg.get('question', '') for msg in conversation_history if msg.get('question')]
            if qa_count < max_qa:
                next_question_obj = self.generate_technical_question(conversation_history, resume_data, job_data, asked_questions)
                next_q_text = (
                    next_question_obj.question
                    if next_question_obj and next_question_obj.question
                    else "Please share another technical problem you led the solution for and explain your approach."
                )
            
                response_parts: List[str] = []
                if evaluation:
                    response_parts.append(f"[Score: {evaluation.score}/5]")
                    if evaluation.feedback:
                        response_parts.append(evaluation.feedback)
                    if evaluation.strengths:
                        response_parts.append(f"Strengths: {', '.join(evaluation.strengths)}")
                    if evaluation.improvements:
                        response_parts.append(f"Improvements: {', '.join(evaluation.improvements)}")
                response_parts.append(f"\nQuestion {qa_count + 1}:\n{next_q_text}")
                return {
                    "message": "\n".join(response_parts) if response_parts else f"Question {qa_count + 1}:\n{next_q_text}",
                    "phase": "qa",
                    "question": next_q_text,
                    "evaluation": {
                        "score": evaluation.score if evaluation else None,
                        "feedback": evaluation.feedback if evaluation else None,
                        "strengths": evaluation.strengths if evaluation else [],
                        "improvements": evaluation.improvements if evaluation else []
                    } if evaluation else None,
                    "qa_count": qa_count
                }
            # 进入总结
            summary = self.generate_final_feedback(conversation_history, resume_data, job_data)
            parts: List[str] = []
            if evaluation:
                parts.append(f"[Last question score: {evaluation.score}/5]")
                if evaluation.feedback:
                    parts.append(evaluation.feedback)
            parts.append(summary.get("message", "The interview has finished. Thank you for your time."))
            return {
                "message": "\n\n".join([p for p in parts if p]),
                "phase": "summary",
                "question": None,
                "evaluation": {
                    "score": evaluation.score if evaluation else None,
                    "feedback": evaluation.feedback if evaluation else None,
                    "strengths": evaluation.strengths if evaluation else [],
                    "improvements": evaluation.improvements if evaluation else []
                } if evaluation else None,
                "qa_count": qa_count,
                "final_feedback": summary.get("final_feedback"),
                "average_score": summary.get("average_score")
            }
        
        # 已结束
        return {
            "message": "The interview has finished. Thank you for your participation! If you want to restart, please click 'Restart' in the frontend.",
            "phase": "summary",
            "question": None,
            "evaluation": None,
            "qa_count": qa_count
        }
    
    def generate_final_feedback(
        self,
        conversation_history: List[Dict[str, Any]],
        resume_data: Optional[Dict[str, Any]],
        job_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate the final feedback report."""
        resume_context = self._build_resume_context(resume_data)
        job_context = self._build_job_context(job_data)
        
        # Collect all evaluations, questions, and user answers
        evaluations = []
        questions_asked = []
        answers_given = []
        
        for msg in conversation_history:
            if msg.get('evaluation'):
                evaluations.append(msg['evaluation'])
            if msg.get('question'):
                questions_asked.append(msg['question'])
            if msg.get('role') == 'user':
                answers_given.append(msg.get('content', ''))
        
        # Compute average score
        scores = [e.get('score') for e in evaluations if e and e.get('score') is not None]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        system_prompt = (
            "You are a senior HR expert and career coach. "
            "You MUST respond in Chinese (中文)."
            "Based on the interview record, write a concise but comprehensive feedback report for the candidate. "
            "The report should include: overall evaluation, key strengths, main areas for improvement, skill profile, and concrete learning suggestions. "
            "Tone: friendly, encouraging, but professional and honest."
        )
        
        interview_summary = "Interview record:\n"
        for i, (q, a) in enumerate(zip(questions_asked, answers_given), 1):
            interview_summary += f"\nQuestion {i}: {q}\nAnswer: {a[:200]}...\n"
            if i < len(evaluations) and evaluations[i-1]:
                eval_data = evaluations[i-1]
                interview_summary += f"Score: {eval_data.get('score', 'N/A')}/5\n"
                if eval_data.get('feedback'):
                    interview_summary += f"Feedback: {eval_data.get('feedback')}\n"
        
        user_prompt = (
            f"Candidate resume:\n{resume_context}\n\n"
            f"Target job information:\n{job_context}\n\n"
            f"{interview_summary}\n\n"
            f"Average score: {avg_score:.2f}/5.00\n\n"
            "Please write the final feedback report in Chinese, covering:\n"
            "1) Overall evaluation;\n"
            "2) 1–2 key strengths;\n"
            "3) 1–2 main areas for improvement with actionable suggestions;\n"
            "4) A brief skill profile for the target role;\n"
            "5) 1–2 concrete learning/practice recommendations."
        )
        
        try:
            feedback = self._call_llm(system_prompt, user_prompt)
            return {
                "message": f"The interview has finished. Here is your overall feedback report:\n\n{feedback}",
                "stage": "feedback",
                "question": None,
                "evaluation": None,
                "final_feedback": feedback,
                "average_score": avg_score
            }
        except Exception as e:
            logging.error(f"Failed to generate final feedback: {e}")
            return {
                "message": f"The interview has finished. Thank you for your participation! Average score: {avg_score:.2f}/5.00",
                "stage": "feedback",
                "question": None,
                "evaluation": None,
                "final_feedback": "Failed to generate detailed feedback. Please try again later.",
                "average_score": avg_score
            }

