#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
后端API服务器
提供简历解析、岗位匹配、智能面试等功能
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

from resume_parser import ResumeParser
from job_matcher import JobMatcher
from interview_agent import InterviewAgent

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 初始化Flask应用
app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 配置
ROOT_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = ROOT_DIR / 'uploads'
UPLOAD_FOLDER.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {'pdf'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# 初始化服务
resume_parser = ResumeParser()
job_matcher = JobMatcher()
interview_agent = InterviewAgent()

# 内存存储（生产环境应使用数据库）
resumes_store: Dict[str, Dict[str, Any]] = {}
jobs_store: List[Dict[str, Any]] = []
interview_sessions: Dict[str, Dict[str, Any]] = {}


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({'status': 'ok', 'message': 'API server is running'})


@app.route('/api/resume/upload', methods=['POST'])
def upload_resume():
    """上传并解析简历"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Only PDF files are allowed'}), 400
        
        # 保存文件
        filename = secure_filename(file.filename)
        file_id = str(uuid.uuid4())
        file_path = UPLOAD_FOLDER / f"{file_id}_{filename}"
        file.save(str(file_path))
        
        logging.info(f"开始解析简历: {file_path}")
        
        # 解析简历
        result = resume_parser.parse_resume(str(file_path))
        
        # 保存到内存存储
        resume_data = {
            'id': file_id,
            'user_id': 'default_user',  # 可以从认证系统获取
            'file_name': filename,
            'file_url': f'/api/resume/file/{file_id}',
            'extracted_info': result['extracted_info'],
            'upload_date': result['upload_date'],
            'status': 'completed',
            'skills': result['skills']
        }
        resumes_store[file_id] = resume_data
        
        logging.info(f"简历解析完成: {file_id}")
        
        return jsonify({
            'resume': {
                'id': resume_data['id'],
                'user_id': resume_data['user_id'],
                'file_name': resume_data['file_name'],
                'file_url': resume_data['file_url'],
                'extracted_info': resume_data['extracted_info'],
                'upload_date': resume_data['upload_date'],
                'status': resume_data['status']
            },
            'skills': resume_data['skills']
        }), 200
        
    except Exception as e:
        logging.error(f"简历解析失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/resume/file/<file_id>', methods=['GET'])
def get_resume_file(file_id: str):
    """获取简历文件"""
    try:
        # 查找文件
        for file_path in UPLOAD_FOLDER.glob(f"{file_id}_*"):
            if file_path.is_file():
                return send_file(str(file_path), mimetype='application/pdf')
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        logging.error(f"获取文件失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/resume/<resume_id>', methods=['GET'])
def get_resume(resume_id: str):
    """获取简历详情"""
    if resume_id not in resumes_store:
        return jsonify({'error': 'Resume not found'}), 404
    
    resume_data = resumes_store[resume_id]
    return jsonify({
        'resume': {
            'id': resume_data['id'],
            'user_id': resume_data['user_id'],
            'file_name': resume_data['file_name'],
            'file_url': resume_data['file_url'],
            'extracted_info': resume_data['extracted_info'],
            'upload_date': resume_data['upload_date'],
            'status': resume_data['status']
        },
        'skills': resume_data['skills']
    }), 200


@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    """获取岗位列表
    
    数据加载优先级：
    1. jobs_enriched.csv - 流水线智能分析后的完整数据（含技能评分）
    2. all_companies_jobs.json - 爬取的JSON数据（可能含技能标签）
    3. bytedance_jobs_enriched.csv - 原始字节跳动数据
    """
    try:
        jobs = []
        data_source = "none"
        
        # 优先级1: 流水线智能分析后的CSV（包含技能评分）
        enriched_csv = ROOT_DIR / 'jobs_enriched.csv'
        if enriched_csv.exists():
            logging.info(f"从智能分析CSV加载岗位: {enriched_csv}")
            df = pd.read_csv(enriched_csv)
            
            for _, row in df.iterrows():
                skill_tags_raw = str(row.get('skill_tags', ''))
                job = {
                    'id': str(row.get('job_id', uuid.uuid4())),
                    'title': str(row.get('job_title', '')),
                    'company': str(row.get('company_name', '')),
                    'description': str(row.get('job_description', '')),
                    'required_skills': parse_skill_tags(skill_tags_raw),
                    'location': str(row.get('location', '')),
                    'salary_range': '面议',
                    'posted_date': '2024-01-01',
                    'job_level1': str(row.get('job_level1', '')),
                    'job_level2': str(row.get('job_level2', '')),
                    'min_degree': str(row.get('min_degree', '')),
                    'degree_priority': str(row.get('degree_priority', '')),
                    'major_requirement': str(row.get('major_requirement_text', '')),
                    'skill_tags_raw': skill_tags_raw,
                    'apply_url': str(row.get('apply_url', '')),
                    'source_url': str(row.get('source_url', '')),
                    'category': str(row.get('category', '')),
                    'requirements': str(row.get('job_requirements', '')),
                }
                jobs.append(job)
            
            data_source = "enriched_csv"
            logging.info(f"从智能分析CSV加载了 {len(jobs)} 个岗位（含技能评分）")
        
        # 优先级2: JSON文件（可能经过智能分析，也可能是原始数据）
        elif (ROOT_DIR / 'all_companies_jobs.json').exists():
            json_file = ROOT_DIR / 'all_companies_jobs.json'
            logging.info(f"从JSON文件加载岗位: {json_file}")
            with open(json_file, 'r', encoding='utf-8') as f:
                raw_jobs = json.load(f)
            
            for raw in raw_jobs:
                # 检查是否有智能分析后的技能标签
                skill_tags_raw = str(raw.get('skill_tags', ''))
                has_enriched = bool(skill_tags_raw and skill_tags_raw != 'nan')
                
                job = {
                    'id': str(raw.get('job_id', uuid.uuid4())),
                    'title': str(raw.get('job_title', '')),
                    'company': str(raw.get('company_name', '')),
                    'description': str(raw.get('job_description', '')),
                    'required_skills': parse_skill_tags(skill_tags_raw) if has_enriched else [],
                    'location': str(raw.get('location', '')),
                    'salary_range': '面议',
                    'posted_date': '2024-01-01',
                    'job_level1': str(raw.get('job_level1', raw.get('job_type', ''))),
                    'job_level2': str(raw.get('job_level2', raw.get('special_program', ''))),
                    'min_degree': str(raw.get('min_degree', '')),
                    'degree_priority': str(raw.get('degree_priority', '')),
                    'major_requirement': str(raw.get('major_requirement', '')),
                    'skill_tags_raw': skill_tags_raw,
                    'apply_url': str(raw.get('apply_url', '')),
                    'source_url': str(raw.get('source_url', '')),
                    'category': str(raw.get('category', '')),
                    'requirements': str(raw.get('job_requirements', '')),
                }
                jobs.append(job)
            
            # 统计有技能标签的岗位
            with_skills = sum(1 for j in jobs if j['required_skills'])
            data_source = "json"
            logging.info(f"从JSON加载了 {len(jobs)} 个岗位（{with_skills}个含技能标签）")
        
        # 优先级3: 原始字节跳动CSV
        elif (ROOT_DIR / 'bytedance_jobs_enriched.csv').exists():
            csv_file = ROOT_DIR / 'bytedance_jobs_enriched.csv'
            logging.info(f"从原始CSV文件加载岗位: {csv_file}")
            df = pd.read_csv(csv_file)
            
            for _, row in df.iterrows():
                skill_tags_raw = str(row.get('skill_tags', ''))
                job = {
                    'id': str(row.get('job_id', uuid.uuid4())),
                    'title': str(row.get('job_title', '')),
                    'company': str(row.get('company_name', '字节跳动')),
                    'description': str(row.get('job_description', '')),
                    'required_skills': parse_skill_tags(skill_tags_raw),
                    'location': str(row.get('location', '')),
                    'salary_range': '面议',
                    'posted_date': '2024-01-01',
                    'job_level1': str(row.get('job_level1', '')),
                    'job_level2': str(row.get('job_level2', '')),
                    'min_degree': str(row.get('min_degree', '')),
                    'skill_tags_raw': skill_tags_raw,
                    'apply_url': str(row.get('apply_url', '')),
                    'source_url': str(row.get('source_url', ''))
                }
                jobs.append(job)
            
            data_source = "bytedance_csv"
            logging.info(f"从原始CSV加载了 {len(jobs)} 个岗位")
        
        else:
            return jsonify({'jobs': [], 'message': 'No jobs file found'}), 200
        
        jobs_store.clear()
        jobs_store.extend(jobs)
        
        return jsonify({
            'jobs': jobs, 
            'total': len(jobs),
            'data_source': data_source,
        }), 200
        
    except Exception as e:
        logging.error(f"加载岗位失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def parse_skill_tags(tag_string: str) -> List[str]:
    """解析技能标签字符串，返回技能名称列表"""
    if not tag_string or tag_string == 'nan':
        return []
    
    skills = []
    # 格式: "技能名 , 分数 , AI | 技能名 , 分数 , AI"
    parts = tag_string.split('|')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # 提取技能名（第一个逗号前的部分）
        skill_name = part.split(',')[0].strip()
        if skill_name:
            skills.append(skill_name)
    
    return skills


@app.route('/api/jobs/match', methods=['POST'])
def match_jobs():
    """岗位匹配"""
    try:
        data = request.json
        resume_id = data.get('resume_id')
        
        if not resume_id or resume_id not in resumes_store:
            return jsonify({'error': 'Resume not found'}), 404
        
        resume_data = resumes_store[resume_id]
        resume_skills = resume_data['skills']
        
        # 加载岗位
        if not jobs_store:
            get_jobs()
        
        # 匹配岗位（已经按匹配度排序）
        matches = job_matcher.match_jobs(resume_skills, jobs_store)
        
        # 返回匹配结果，已经按匹配度从高到低排序
        return jsonify({
            'matches': matches,
            'resume_id': resume_id
        }), 200
        
    except Exception as e:
        logging.error(f"岗位匹配失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/interview/start', methods=['POST'])
def start_interview():
    """开始面试"""
    try:
        data = request.json
        resume_id = data.get('resume_id')
        job_id = data.get('job_id')
        
        if resume_id and resume_id not in resumes_store:
            return jsonify({'error': 'Resume not found'}), 404
        
        session_id = str(uuid.uuid4())
        
        # 获取简历和岗位信息
        resume_data = resumes_store.get(resume_id) if resume_id else None
        job_data = next((j for j in jobs_store if j['id'] == job_id), None) if job_id else None
        
        # 初始化面试会话
        interview_sessions[session_id] = {
            'id': session_id,
            'resume_id': resume_id,
            'job_id': job_id,
            'started_at': datetime.now().isoformat(),
            'status': 'active',
            'messages': [],
            'stage': 'greeting',  # 当前阶段：greeting -> qa -> summary
            'phase': 'greeting',
            'qa_count': 0,
            'max_qa': 5
        }
        
        # 生成开场白（不出题）
        start_result = interview_agent.start_interview(resume_data, job_data)
        
        # 添加开场白消息（仅开场白与自我介绍提示）
        greeting_msg = {
            'id': str(uuid.uuid4()),
            'session_id': session_id,
            'role': 'assistant',
            'content': f"{start_result.get('greeting', '')}\n\n{start_result.get('self_intro', '')}",
            'created_at': datetime.now().isoformat(),
            'question': None,
            'stage': start_result.get('stage', 'greeting')
        }
        interview_sessions[session_id]['messages'].append(greeting_msg)
        interview_sessions[session_id]['stage'] = start_result.get('stage', 'greeting')
        interview_sessions[session_id]['phase'] = start_result.get('stage', 'greeting')
        
        return jsonify({
            'session_id': session_id,
            'message': f"{start_result.get('greeting', '')}\n\n{start_result.get('self_intro', '')}",
            'question': None,
            'stage': start_result.get('stage', 'greeting')
        }), 200
        
    except Exception as e:
        logging.error(f"开始面试失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/interview/<session_id>/message', methods=['POST'])
def send_interview_message(session_id: str):
    """发送面试消息"""
    try:
        if session_id not in interview_sessions:
            return jsonify({'error': 'Session not found'}), 404
        
        data = request.json
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        session = interview_sessions[session_id]
        current_stage = session.get('stage', 'greeting')
        
        # 添加用户消息
        user_msg = {
            'id': str(uuid.uuid4()),
            'session_id': session_id,
            'role': 'user',
            'content': user_message,
            'created_at': datetime.now().isoformat()
        }
        session['messages'].append(user_msg)
        
        # 获取简历和岗位信息
        resume_data = resumes_store.get(session['resume_id']) if session['resume_id'] else None
        job_data = next((j for j in jobs_store if j['id'] == session['job_id']), None) if session['job_id'] else None
        
        # 生成AI回复
        response = interview_agent.respond(
            user_message,
            session['messages'],
            resume_data,
            job_data,
            session_state=session
        )
        
        # 更新阶段与计数器
        new_phase = response.get('phase', session.get('phase', current_stage))
        session['phase'] = new_phase
        session['stage'] = new_phase
        if 'qa_count' in response:
            session['qa_count'] = response['qa_count']
        
        # 构建回复内容
        reply_content = response.get('message', '')
        
        # 添加AI回复
        assistant_msg = {
            'id': str(uuid.uuid4()),
            'session_id': session_id,
            'role': 'assistant',
            'content': reply_content,
            'created_at': datetime.now().isoformat(),
            'question': response.get('question'),
            'evaluation': response.get('evaluation'),
            'stage': new_phase
        }
        session['messages'].append(assistant_msg)
        
        return jsonify({
            'message': reply_content,
            'session_id': session_id,
            'stage': new_phase,
            'question': response.get('question'),
            'evaluation': response.get('evaluation'),
            'final_feedback': response.get('final_feedback'),
            'average_score': response.get('average_score')
        }), 200
        
    except Exception as e:
        logging.error(f"发送消息失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/interview/<session_id>', methods=['GET'])
def get_interview_session(session_id: str):
    """获取面试会话"""
    if session_id not in interview_sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    session = interview_sessions[session_id]
    return jsonify({
        'session': {
            'id': session['id'],
            'resume_id': session['resume_id'],
            'job_id': session['job_id'],
            'started_at': session['started_at'],
            'status': session['status']
        },
        'messages': session['messages']
    }), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

