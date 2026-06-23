#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
岗位匹配模块
功能：
1. 解析岗位技能标签
2. 与简历技能进行匹配
3. 计算匹配分数（优先匹配标签数量，其次匹配分数高低）
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

logging.basicConfig(level=logging.INFO)

# Match a standalone 1-5 score, not a digit embedded in a skill name (Vue3,
# Angular2, Python3): bound the digit by non-word characters so a version
# number in the skill name isn't mistaken for the score.
_SCORE_RE = re.compile(r"(?<!\w)([1-5])(?:\.0)?(?!\w)")


def _normalize_skill_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().lower()


def _clean_skill_name(name: str) -> str:
    return name.strip().strip(" -:：()[]{}")


class JobMatcher:
    """岗位匹配器"""
    
    def __init__(self):
        pass
    
    def parse_job_skills(self, skill_tags_raw: str) -> List[Tuple[str, int]]:
        """
        解析岗位技能标签字符串
        支持格式: "技能名 , 分数 , AI" / "技能名 %> 分数 , AI" / "技能名: 分数"
        返回: [(技能名, 分数), ...]
        """
        if not skill_tags_raw or str(skill_tags_raw).lower() == 'nan':
            return []

        skills_by_key: Dict[str, Tuple[str, int]] = {}
        parts = str(skill_tags_raw).split('|')

        for part in parts:
            part = part.strip()
            if not part:
                continue

            score_match = _SCORE_RE.search(part)
            score = int(score_match.group(1)) if score_match else 3

            if "%>" in part:
                skill_name = part.split("%>", 1)[0]
            elif score_match:
                skill_name = part[:score_match.start()]
                skill_name = skill_name.rsplit(",", 1)[0]
                skill_name = skill_name.rsplit("，", 1)[0]
            else:
                skill_name = part.split(",", 1)[0].split("，", 1)[0]

            skill_name = _clean_skill_name(skill_name)
            if not skill_name:
                continue

            key = _normalize_skill_name(skill_name)
            existing = skills_by_key.get(key)
            if existing is None or score > existing[1]:
                skills_by_key[key] = (skill_name, score)

        return list(skills_by_key.values())

    def match_jobs(
        self,
        resume_skills: List[Dict[str, Any]],
        jobs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        匹配岗位
        参数:
            resume_skills: 简历技能列表，格式: [{"skill_name": "Python", "score": 4}, ...]
            jobs: 岗位列表
        返回:
            匹配结果列表，按匹配度排序
        """
        # 构建简历技能字典（技能名 -> 分数）
        resume_skill_dict = {}
        for skill in resume_skills:
            name = str(skill.get('skill_name', '')).strip()
            if not name:
                continue
            resume_skill_dict[_normalize_skill_name(name)] = int(skill.get('score', 0) or 0)
        
        matches = []
        
        for job in jobs:
            # 解析岗位技能
            job_skills_raw = job.get('skill_tags_raw', '')
            job_skills = self.parse_job_skills(job_skills_raw)
            
            if not job_skills:
                # 如果没有技能标签，使用required_skills
                job_skill_names = job.get('required_skills', [])
                job_skills = [(name, 3) for name in job_skill_names]  # 默认3分
            
            # 计算匹配
            match_result = self._calculate_match(resume_skill_dict, job_skills)
            
            matches.append({
                'job_id': job['id'],
                'job': job,
                'match_score': match_result['match_score'],
                'matched_skills': match_result['matched_skills'],
                'missing_skills': match_result['missing_skills'],
                'match_details': match_result['details']
            })
        
        # 排序：优先匹配标签数量，其次匹配分数
        matches.sort(key=lambda x: (
            -len(x['matched_skills']),  # 匹配标签数量（降序）
            -x['match_score']  # 匹配分数（降序）
        ))

        return matches

    def top_skill_gaps(
        self,
        matches: List[Dict[str, Any]],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        汇总所有匹配岗位的技能缺口，找出最该优先补齐的技能。
        遍历 match_jobs 的结果，统计每个缺口技能在多少个岗位里出现；
        出现得越多，说明越是当前匹配岗位的硬通货、最该先学。
        参数:
            matches: match_jobs 的返回结果
            limit: 返回前 N 个最高频的缺口技能
        返回:
            [{"skill": 技能名, "job_count": 出现岗位数}, ...]，
            按 job_count 降序、技能名升序排列
        """
        counts: Dict[str, int] = {}
        display: Dict[str, str] = {}
        for match in matches:
            # 同一岗位内按归一化名去重，避免重复技能名被多算
            seen = set()
            for skill in match.get('missing_skills', []):
                key = _normalize_skill_name(str(skill))
                if not key or key in seen:
                    continue
                seen.add(key)
                counts[key] = counts.get(key, 0) + 1
                display.setdefault(key, _clean_skill_name(str(skill)))

        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return [
            {'skill': display[key], 'job_count': count}
            for key, count in ranked[:limit]
        ]

    def _calculate_match(
        self,
        resume_skills: Dict[str, int],
        job_skills: List[Tuple[str, int]]
    ) -> Dict[str, Any]:
        """
        计算匹配度
        策略：
        1. 优先匹配标签数量（有多少个技能匹配）
        2. 其次匹配分数高低（分数越高越好）
        """
        matched_skills = []
        missing_skills: List[str] = []
        total_score = 0
        match_count = 0

        for job_skill_name, job_score in job_skills:
            # 精确匹配
            normalized_job_skill = _normalize_skill_name(job_skill_name)
            if normalized_job_skill in resume_skills:
                resume_score = resume_skills[normalized_job_skill]
                matched_skills.append({
                    'skill_name': job_skill_name,
                    'resume_score': resume_score,
                    'job_score': job_score,
                    'match_type': 'exact'
                })
                total_score += resume_score
                match_count += 1
            else:
                # 模糊匹配（包含关系）：在所有命中里挑简历分最高的，
                # 否则结果会取决于简历技能的字典顺序、同一份输入算出不同分。
                best_name = None
                best_score = None
                for resume_skill_name, resume_score in resume_skills.items():
                    # Substring fuzzy match, but skip it when the shorter name is
                    # a single character: a one-letter skill like "R" or "C"
                    # otherwise matches inside any word containing that letter
                    # ("R" in "React", "C" in "Scala"), a false positive. Those
                    # rely on exact match instead; "ml", "python3" etc. (>= 2
                    # chars) still fuzzy-match as before.
                    if min(len(normalized_job_skill), len(resume_skill_name)) < 2:
                        continue
                    if (normalized_job_skill in resume_skill_name or
                        resume_skill_name in normalized_job_skill):
                        if best_score is None or resume_score > best_score:
                            best_name = resume_skill_name
                            best_score = resume_score
                if best_score is not None:
                    matched_skills.append({
                        'skill_name': job_skill_name,
                        'resume_skill_name': best_name,
                        'resume_score': best_score,
                        'job_score': job_score,
                        'match_type': 'fuzzy'
                    })
                    total_score += best_score
                    match_count += 1
                else:
                    # 岗位要求但简历里没有的技能，作为技能差距反馈给求职者
                    missing_skills.append(job_skill_name)

        # 计算匹配分数（0-100）
        if not job_skills:
            match_score = 0
        else:
            # 匹配率（匹配的技能数 / 岗位要求的技能数）
            match_rate = match_count / len(job_skills)
            # 平均分数（匹配技能的平均分 / 5）
            avg_score = (total_score / match_count) if match_count > 0 else 0
            score_rate = avg_score / 5.0
            
            # 综合分数：匹配率权重60%，分数权重40%
            match_score = int(match_rate * 60 + score_rate * 40)
            match_score = min(100, max(0, match_score))  # 限制在0-100
        
        return {
            'match_score': match_score,
            'matched_skills': [m['skill_name'] for m in matched_skills],
            'missing_skills': missing_skills,
            'details': {
                'match_count': match_count,
                'total_job_skills': len(job_skills),
                'match_rate': match_count / len(job_skills) if job_skills else 0,
                'avg_resume_score': total_score / match_count if match_count > 0 else 0,
                'matched_skills_detail': matched_skills
            }
        }

