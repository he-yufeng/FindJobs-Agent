export interface TrackedApplication {
  job_id: string;
  status: string;
  note: string;
  updated_at: string;
  job_title: string;
  company_name: string;
}

interface ApplicationListResponse {
  success: boolean;
  applications: TrackedApplication[];
  statuses: string[];
  error?: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok || data.success === false) {
    throw new Error(data.error || `请求失败 (${resp.status})`);
  }
  return data as T;
}

export function getApplications(): Promise<ApplicationListResponse> {
  return request<ApplicationListResponse>('/api/applications');
}

export function setApplicationStatus(jobId: string, status: string, note: string): Promise<void> {
  return request<void>(`/api/applications/${encodeURIComponent(jobId)}`, {
    method: 'PUT',
    body: JSON.stringify({ status, note }),
  });
}

export function removeApplication(jobId: string): Promise<void> {
  return request<void>(`/api/applications/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
}
