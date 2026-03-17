/**
 * Mission Control API Client
 *
 * Connects the dashboard to the FastAPI backend.
 * All data flows through here — the dashboard never
 * touches the database directly.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

// --- Projects ---

export interface Project {
  id: string;
  name: string;
  description: string;
  status: 'active' | 'planning' | 'paused' | 'archived';
  color: string;
  url?: string;
  task_count: number;
  agent_count: number;
  created_at: string;
}

export const projects = {
  list: () => request<Project[]>('/api/projects'),
  create: (data: Partial<Project>) => request<{ id: string }>('/api/projects', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Project>) => request<{ updated: boolean }>(`/api/projects/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) => request<{ deleted: boolean }>(`/api/projects/${id}`, { method: 'DELETE' }),
};

// --- Tasks ---

export interface Task {
  id: string;
  text: string;
  status: 'todo' | 'in_progress' | 'blocked' | 'done';
  priority: 'critical' | 'high' | 'medium' | 'low';
  project_id?: string;
  source: string;
  tags: string[];
  due_date?: string;
  created_at: string;
}

export const tasks = {
  list: (params?: { status?: string; project_id?: string }) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    return request<Task[]>(`/api/tasks${qs ? '?' + qs : ''}`);
  },
  create: (data: Partial<Task>) => request<{ id: string }>('/api/tasks', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Task>) => request<{ updated: boolean }>(`/api/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) => request<{ deleted: boolean }>(`/api/tasks/${id}`, { method: 'DELETE' }),
};

// --- Ideas ---

export interface Idea {
  id: string;
  text: string;
  tags: string[];
  source: string;
  score?: number;
  validation_notes?: string;
  project_id?: string;
  created_at: string;
}

export const ideas = {
  list: () => request<Idea[]>('/api/ideas'),
  create: (data: Partial<Idea>) => request<{ id: string }>('/api/ideas', { method: 'POST', body: JSON.stringify(data) }),
  delete: (id: string) => request<{ deleted: boolean }>(`/api/ideas/${id}`, { method: 'DELETE' }),
};

// --- Reading List ---

export interface ReadingItem {
  id: string;
  title: string;
  url?: string;
  is_read: boolean;
  notes?: string;
  tags: string[];
  source: string;
  created_at: string;
}

export const reading = {
  list: (showRead = false) => request<ReadingItem[]>(`/api/reading?show_read=${showRead}`),
  create: (data: Partial<ReadingItem>) => request<{ id: string }>('/api/reading', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<ReadingItem>) => request<{ updated: boolean }>(`/api/reading/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) => request<{ deleted: boolean }>(`/api/reading/${id}`, { method: 'DELETE' }),
};

// --- Agents ---

export interface AgentRun {
  id: string;
  status: string;
  cost_usd: number;
  started_at: string;
}

export interface Agent {
  id: string;
  name: string;
  slug: string;
  description: string;
  agent_type: string;
  status: 'idle' | 'running' | 'error' | 'disabled';
  model: string;
  schedule_type?: string;
  schedule_value?: string;
  project_id?: string;
  last_run_at?: string;
  recent_runs: AgentRun[];
}

export const agents = {
  list: () => request<Agent[]>('/api/agents'),
  run: (id: string) => request<{ run_id: string; status: string }>(`/api/agents/${id}/run`, { method: 'POST' }),
  stop: (id: string) => request<{ status: string }>(`/api/agents/${id}/stop`, { method: 'POST' }),
  runs: (id: string, limit = 20) => request<AgentRun[]>(`/api/agents/${id}/runs?limit=${limit}`),
};

// --- Health ---

export interface HealthStatus {
  status: string;
  database: string;
  llm_provider: string;
  telegram: string;
}

export const health = {
  check: () => request<HealthStatus>('/health'),
};

// --- WebSocket ---

export function connectWebSocket(onMessage: (event: { type: string; data: any }) => void): WebSocket | null {
  const wsUrl = API_BASE.replace(/^http/, 'ws') + '/ws';
  try {
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        onMessage(parsed);
      } catch {}
    };
    ws.onclose = () => {
      // Auto-reconnect after 3s
      setTimeout(() => connectWebSocket(onMessage), 3000);
    };
    return ws;
  } catch {
    return null;
  }
}
