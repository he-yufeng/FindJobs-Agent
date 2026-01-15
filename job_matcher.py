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


class JobMatcher:
    """岗位匹配器"""
    
    def __init__(self):
        pass
    
    def parse_job_skills(self, skill_tags_raw: str) -> List[Tuple[str, int]]:
        """
        解析岗位技能标签字符串
        格式: "技能名 , 分数 , AI | 技能名 , 分数 , AI"
        返回: [(技能名, 分数), ...]
        """
        if not skill_tags_raw or skill_tags_raw == 'nan':
            return []
        
        skills = []
        parts = skill_tags_raw.split('|')
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # 解析格式: "技能名 , 分数 , AI"
            segments = [s.strip() for s in part.split(',')]
            if len(segments) >= 2:
                skill_name = segments[0]
                try:
                    score = int(segments[1])
                    if skill_name:
                        skills.append((skill_name, score))
                except ValueError:
                    # 如果分数不是数字，默认给3分
                    if skill_name:
                        skills.append((skill_name, 3))
        
        return skills
    
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
        resume_skill_dict = {
            skill['skill_name']: skill['score']
            for skill in resume_skills
        }
        
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
                'match_details': match_result['details']
            })
        
        # 排序：优先匹配标签数量，其次匹配分数
        matches.sort(key=lambda x: (
            -len(x['matched_skills']),  # 匹配标签数量（降序）
            -x['match_score']  # 匹配分数（降序）
        ))
        
        return matches
    
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
        total_score = 0
        match_count = 0
        
        for job_skill_name, job_score in job_skills:
            # 精确匹配
            if job_skill_name in resume_skills:
                resume_score = resume_skills[job_skill_name]
                matched_skills.append({
                    'skill_name': job_skill_name,
                    'resume_score': resume_score,
                    'job_score': job_score,
                    'match_type': 'exact'
                })
                total_score += resume_score
                match_count += 1
            else:
                # 模糊匹配（包含关系）
                matched = False
                for resume_skill_name, resume_score in resume_skills.items():
                    if (job_skill_name.lower() in resume_skill_name.lower() or
                        resume_skill_name.lower() in job_skill_name.lower()):
                        matched_skills.append({
                            'skill_name': job_skill_name,
                            'resume_skill_name': resume_skill_name,
                            'resume_score': resume_score,
                            'job_score': job_score,
                            'match_type': 'fuzzy'
                        })
                        total_score += resume_score
                        match_count += 1
                        matched = True
                        break
        
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
            'details': {
                'match_count': match_count,
                'total_job_skills': len(job_skills),
                'match_rate': match_count / len(job_skills) if job_skills else 0,
                'avg_resume_score': total_score / match_count if match_count > 0 else 0,
                'matched_skills_detail': matched_skills
            }
        }

