/*
  # Resume Analysis Platform Schema

  1. New Tables
    - `resumes`
      - `id` (uuid, primary key)
      - `user_id` (uuid, foreign key to auth.users)
      - `file_name` (text)
      - `file_url` (text)
      - `extracted_info` (jsonb) - stores personal info, education, experience
      - `upload_date` (timestamptz)
      - `status` (text) - processing, completed, failed
    
    - `resume_skills`
      - `id` (uuid, primary key)
      - `resume_id` (uuid, foreign key to resumes)
      - `skill_name` (text)
      - `score` (integer) - 1 to 5 rating
      - `category` (text) - programming, tools, soft skills, etc.
    
    - `job_positions`
      - `id` (uuid, primary key)
      - `title` (text)
      - `company` (text)
      - `description` (text)
      - `required_skills` (text[]) - array of skill keywords
      - `location` (text)
      - `salary_range` (text)
      - `posted_date` (timestamptz)
    
    - `job_matches`
      - `id` (uuid, primary key)
      - `resume_id` (uuid, foreign key to resumes)
      - `job_id` (uuid, foreign key to job_positions)
      - `match_score` (integer) - 0 to 100
      - `matched_skills` (text[])
      - `created_at` (timestamptz)
    
    - `interview_sessions`
      - `id` (uuid, primary key)
      - `resume_id` (uuid, foreign key to resumes)
      - `job_id` (uuid, foreign key to job_positions, nullable)
      - `started_at` (timestamptz)
      - `status` (text) - active, completed
    
    - `interview_messages`
      - `id` (uuid, primary key)
      - `session_id` (uuid, foreign key to interview_sessions)
      - `role` (text) - user, assistant
      - `content` (text)
      - `created_at` (timestamptz)

  2. Security
    - Enable RLS on all tables
    - Users can only access their own data
*/

CREATE TABLE IF NOT EXISTS resumes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  file_name text NOT NULL,
  file_url text NOT NULL,
  extracted_info jsonb DEFAULT '{}'::jsonb,
  upload_date timestamptz DEFAULT now(),
  status text DEFAULT 'processing'
);

CREATE TABLE IF NOT EXISTS resume_skills (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  resume_id uuid REFERENCES resumes(id) ON DELETE CASCADE,
  skill_name text NOT NULL,
  score integer CHECK (score >= 1 AND score <= 5),
  category text DEFAULT 'general'
);

CREATE TABLE IF NOT EXISTS job_positions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  company text NOT NULL,
  description text NOT NULL,
  required_skills text[] DEFAULT ARRAY[]::text[],
  location text DEFAULT '',
  salary_range text DEFAULT '',
  posted_date timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS job_matches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  resume_id uuid REFERENCES resumes(id) ON DELETE CASCADE,
  job_id uuid REFERENCES job_positions(id) ON DELETE CASCADE,
  match_score integer CHECK (match_score >= 0 AND match_score <= 100),
  matched_skills text[] DEFAULT ARRAY[]::text[],
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS interview_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  resume_id uuid REFERENCES resumes(id) ON DELETE CASCADE,
  job_id uuid REFERENCES job_positions(id) ON DELETE SET NULL,
  started_at timestamptz DEFAULT now(),
  status text DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS interview_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid REFERENCES interview_sessions(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('user', 'assistant')),
  content text NOT NULL,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE resumes ENABLE ROW LEVEL SECURITY;
ALTER TABLE resume_skills ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE interview_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE interview_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own resumes"
  ON resumes FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own resumes"
  ON resumes FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own resumes"
  ON resumes FOR UPDATE
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own resumes"
  ON resumes FOR DELETE
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can view own resume skills"
  ON resume_skills FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM resumes
      WHERE resumes.id = resume_skills.resume_id
      AND resumes.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can insert own resume skills"
  ON resume_skills FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM resumes
      WHERE resumes.id = resume_skills.resume_id
      AND resumes.user_id = auth.uid()
    )
  );

CREATE POLICY "Everyone can view job positions"
  ON job_positions FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Users can view own job matches"
  ON job_matches FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM resumes
      WHERE resumes.id = job_matches.resume_id
      AND resumes.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can view own interview sessions"
  ON interview_sessions FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM resumes
      WHERE resumes.id = interview_sessions.resume_id
      AND resumes.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can insert own interview sessions"
  ON interview_sessions FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM resumes
      WHERE resumes.id = interview_sessions.resume_id
      AND resumes.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can view own interview messages"
  ON interview_messages FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM interview_sessions
      JOIN resumes ON resumes.id = interview_sessions.resume_id
      WHERE interview_sessions.id = interview_messages.session_id
      AND resumes.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can insert own interview messages"
  ON interview_messages FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM interview_sessions
      JOIN resumes ON resumes.id = interview_sessions.resume_id
      WHERE interview_sessions.id = interview_messages.session_id
      AND resumes.user_id = auth.uid()
    )
  );

CREATE INDEX idx_resumes_user_id ON resumes(user_id);
CREATE INDEX idx_resume_skills_resume_id ON resume_skills(resume_id);
CREATE INDEX idx_job_matches_resume_id ON job_matches(resume_id);
CREATE INDEX idx_interview_messages_session_id ON interview_messages(session_id);