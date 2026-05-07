import type { JobMatch, JobPosition, Resume, ResumeSkill } from '../types';

const API_BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

type UploadResumeResponse = {
  resume: Resume;
  skills: ResumeSkill[];
};

type JobsResponse = {
  jobs: JobPosition[];
};

type JobMatchResponse = {
  matches: JobMatch[];
};

type StartInterviewResponse = {
  session_id: string;
  message: string;
};

type InterviewMessageResponse = {
  message: string;
};

async function readJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  const body = text ? JSON.parse(text) : {};

  if (!response.ok) {
    const message =
      typeof body?.error === 'string'
        ? body.error
        : typeof body?.message === 'string'
          ? body.message
          : `Request failed with ${response.status}`;
    throw new Error(message);
  }

  return body as T;
}

export async function simulateResumeUpload(file: File): Promise<UploadResumeResponse> {
  const form = new FormData();
  form.append('file', file);

  const response = await fetch(`${API_BASE}/resume/upload`, {
    method: 'POST',
    body: form,
  });

  return readJson<UploadResumeResponse>(response);
}

export async function getJobs(): Promise<JobPosition[]> {
  const response = await fetch(`${API_BASE}/jobs`);
  const data = await readJson<JobsResponse>(response);
  return data.jobs;
}

export async function simulateJobMatching(resumeId: string): Promise<JobMatch[]> {
  const response = await fetch(`${API_BASE}/jobs/match`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resume_id: resumeId }),
  });
  const data = await readJson<JobMatchResponse>(response);
  return data.matches;
}

export async function startInterview(
  resumeId: string | undefined,
  jobId: string | undefined,
): Promise<{ sessionId: string; message: string }> {
  const response = await fetch(`${API_BASE}/interview/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resume_id: resumeId, job_id: jobId }),
  });
  const data = await readJson<StartInterviewResponse>(response);
  return { sessionId: data.session_id, message: data.message };
}

export async function simulateInterviewChat(
  sessionId: string,
  message: string,
): Promise<string> {
  const response = await fetch(`${API_BASE}/interview/${sessionId}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  const data = await readJson<InterviewMessageResponse>(response);
  return data.message;
}
