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

// --- Habits ---

export interface Habit {
  id: string;
  name: string;
  description: string;
  frequency: 'daily' | 'weekly' | 'custom';
  current_streak: number;
  best_streak: number;
  total_completions: number;
  is_active: boolean;
  color: string;
  completed_today: boolean;
  project_id?: string;
  created_at: string;
}

export const habits = {
  list: (activeOnly = true) => request<Habit[]>(`/api/habits?active_only=${activeOnly}`),
  create: (data: Partial<Habit>) => request<{ id: string }>('/api/habits', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Habit>) => request<{ updated: boolean }>(`/api/habits/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  complete: (id: string) => request<{ current_streak: number }>(`/api/habits/${id}/complete`, { method: 'POST' }),
  uncomplete: (id: string) => request<{ uncompleted: boolean }>(`/api/habits/${id}/uncomplete`, { method: 'POST' }),
  delete: (id: string) => request<{ deleted: boolean }>(`/api/habits/${id}`, { method: 'DELETE' }),
};

// --- Goals ---

export interface KeyResult {
  id: string;
  title: string;
  target_value: number;
  current_value: number;
  unit: string;
  progress: number;
}

export interface Goal {
  id: string;
  title: string;
  description: string;
  status: 'active' | 'completed' | 'abandoned';
  target_date?: string;
  progress: number;
  project_id?: string;
  tags: string[];
  key_results: KeyResult[];
  created_at: string;
}

export const goals = {
  list: (status?: string) => {
    const qs = status ? `?status=${status}` : '';
    return request<Goal[]>(`/api/goals${qs}`);
  },
  create: (data: Partial<Goal>) => request<{ id: string }>('/api/goals', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Goal>) => request<{ updated: boolean }>(`/api/goals/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) => request<{ deleted: boolean }>(`/api/goals/${id}`, { method: 'DELETE' }),
  createKeyResult: (goalId: string, data: Partial<KeyResult>) =>
    request<{ id: string }>(`/api/goals/${goalId}/key-results`, { method: 'POST', body: JSON.stringify(data) }),
  updateKeyResult: (goalId: string, krId: string, data: Partial<KeyResult>) =>
    request<{ updated: boolean }>(`/api/goals/${goalId}/key-results/${krId}`, { method: 'PATCH', body: JSON.stringify(data) }),
};

// --- Journal ---

export interface JournalEntry {
  id: string;
  content: string;
  mood?: 'great' | 'good' | 'okay' | 'low' | 'bad';
  energy?: number;
  tags: string[];
  wins: string[];
  challenges: string[];
  gratitude: string[];
  source: string;
  created_at: string;
}

export const journal = {
  list: (limit = 30) => request<JournalEntry[]>(`/api/journal?limit=${limit}`),
  create: (data: Partial<JournalEntry>) => request<{ id: string }>('/api/journal', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<JournalEntry>) => request<{ updated: boolean }>(`/api/journal/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) => request<{ deleted: boolean }>(`/api/journal/${id}`, { method: 'DELETE' }),
};

// --- Approvals ---

export interface Approval {
  id: string;
  agent_id: string;
  agent_name: string;
  run_id: string;
  summary: string;
  actions: any[];
  action_count: number;
  created_at: string;
  expires_at?: string;
}

export const approvals = {
  list: () => request<Approval[]>('/api/approvals'),
  approve: (id: string) => request<{ status: string }>(`/api/approvals/${id}/approve`, { method: 'POST' }),
  reject: (id: string) => request<{ status: string }>(`/api/approvals/${id}/reject`, { method: 'POST' }),
};

// --- Search ---

export interface SearchResult {
  type: string;
  id: string;
  title: string;
  status?: string;
  priority?: string;
  tags?: string[];
  created_at: string;
}

export interface SearchResponse {
  query: string;
  total: number;
  results: SearchResult[];
}

export const search = {
  query: (q: string, entityTypes = 'all', limit = 20) =>
    request<SearchResponse>(`/api/search?q=${encodeURIComponent(q)}&entity_types=${entityTypes}&limit=${limit}`),
};

// --- Notifications ---

export interface Notification {
  id: string;
  title: string;
  body: string;
  category: 'info' | 'success' | 'warning' | 'error' | 'approval';
  source: string;
  is_read: boolean;
  action_url?: string;
  created_at: string;
}

export const notifications = {
  list: (unreadOnly = false, limit = 50) =>
    request<Notification[]>(`/api/notifications?unread_only=${unreadOnly}&limit=${limit}`),
  unreadCount: () => request<{ unread: number }>('/api/notifications/count'),
  markRead: (id: string) => request<{ read: boolean }>(`/api/notifications/${id}/read`, { method: 'POST' }),
  markAllRead: () => request<{ read_all: boolean }>('/api/notifications/read-all', { method: 'POST' }),
};

// --- Export ---

export const dataExport = {
  jsonUrl: (entities = 'all') => `${API_BASE}/api/export/json?entities=${entities}`,
  csvUrl: (entityType: string) => `${API_BASE}/api/export/csv/${entityType}`,
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
