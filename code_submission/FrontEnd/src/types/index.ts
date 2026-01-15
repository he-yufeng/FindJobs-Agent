export interface Resume {
  id: string;
  user_id: string;
  file_name: string;
  file_url: string;
  extracted_info: {
    name?: string;
    email?: string;
    phone?: string;
    education?: Array<{
      school: string;
      degree: string;
      major: string;
      year: string;
    }>;
    experience?: Array<{
      company: string;
      position: string;
      duration: string;
      description: string;
    }>;
  };
  upload_date: string;
  status: 'processing' | 'completed' | 'failed';
}

export interface ResumeSkill {
  id: string;
  resume_id: string;
  skill_name: string;
  score: number;
  category: string;
}

export interface JobPosition {
  id: string;
  title: string;
  company: string;
  description: string;
  required_skills: string[];
  location: string;
  salary_range: string;
  posted_date: string;
  apply_url?: string;
  source_url?: string;
}

export interface JobMatch {
  id?: string;
  resume_id?: string;
  job_id: string;
  match_score: number;
  matched_skills: string[];
  created_at?: string;
  job?: JobPosition;
  match_details?: {
    match_count: number;
    total_job_skills: number;
    match_rate: number;
    avg_resume_score: number;
    matched_skills_detail: any[];
  };
}

export interface InterviewSession {
  id: string;
  resume_id: string;
  job_id?: string;
  started_at: string;
  status: 'active' | 'completed';
}

export interface InterviewMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}
