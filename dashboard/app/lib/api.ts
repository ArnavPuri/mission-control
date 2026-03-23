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
  status: 'active' | 'planning' | 'launched' | 'paused' | 'archived';
  color: string;
  url?: string;
  metadata?: Record<string, unknown>;
  task_count: number;
  open_task_count: number;
  content_count: number;
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

export interface AgentDetail extends Agent {
  max_budget_usd: number;
  prompt_template: string;
  tools: string[];
  data_reads: string[];
  data_writes: string[];
  config: Record<string, unknown>;
  skill_file: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface RunDetailResponse {
  id: string;
  agent_id: string;
  status: string;
  trigger: string;
  tokens_used: number;
  cost_usd: number;
  error: string | null;
  output_data: Record<string, unknown> | null;
  transcript: { role: string; content: string }[] | null;
  started_at: string;
  completed_at: string | null;
}

export const agents = {
  list: () => request<Agent[]>('/api/agents'),
  get: (id: string) => request<AgentDetail>(`/api/agents/${id}`),
  create: (data: Partial<AgentDetail>) => request<AgentDetail>('/api/agents', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<AgentDetail>) => request<AgentDetail>(`/api/agents/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  triggerRun: (id: string) => request<{ run_id: string; status: string }>(`/api/agents/${id}/run`, { method: 'POST' }),
  runs: (id: string, limit = 20) => request<AgentRun[]>(`/api/agents/${id}/runs?limit=${limit}`),
  runDetail: (agentId: string, runId: string) => request<RunDetailResponse>(`/api/agents/${agentId}/runs/${runId}`),
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

// --- Notes ---

export interface Note {
  id: string;
  title: string;
  content: string;
  tags: string[];
  is_pinned: boolean;
  project_id?: string;
  source: string;
  created_at: string;
  updated_at: string;
}

export const notes = {
  list: (tag?: string) => request<Note[]>(`/api/notes${tag ? `?tag=${encodeURIComponent(tag)}` : ''}`),
  create: (data: Partial<Note>) => request<{ id: string }>('/api/notes', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Note>) => request<{ updated: boolean }>(`/api/notes/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) => request<{ deleted: boolean }>(`/api/notes/${id}`, { method: 'DELETE' }),
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
  count: () => request<{ unread: number }>('/api/notifications/count'),
  markRead: (id: string) => request<{ read: boolean }>(`/api/notifications/${id}/read`, { method: 'POST' }),
  markAllRead: () => request<{ read_all: boolean }>('/api/notifications/read-all', { method: 'POST' }),
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

// --- Marketing Signals ---

export interface MarketingSignal {
  id: string;
  title: string;
  body: string;
  source: string;
  source_type: string;
  source_url: string | null;
  relevance_score: number;
  signal_type: string;
  status: 'new' | 'reviewed' | 'acted_on' | 'dismissed';
  channel_metadata: Record<string, unknown>;
  project_id: string | null;
  agent_id: string | null;
  tags: string[];
  created_at: string;
  updated_at: string | null;
}

export const marketingSignals = {
  list: (params?: { status?: string; source_type?: string; signal_type?: string; project_id?: string }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status', params.status);
    if (params?.source_type) qs.set('source_type', params.source_type);
    if (params?.signal_type) qs.set('signal_type', params.signal_type);
    if (params?.project_id) qs.set('project_id', params.project_id);
    const query = qs.toString();
    return request<MarketingSignal[]>(`/api/mkt-signals${query ? `?${query}` : ''}`);
  },
  update: (id: string, data: Partial<MarketingSignal>) =>
    request<MarketingSignal>(`/api/mkt-signals/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
};

// --- Marketing Content ---

export interface MarketingContent {
  id: string;
  title: string;
  body: string;
  channel: string;
  status: 'draft' | 'approved' | 'posted' | 'archived';
  source: string;
  signal_id: string | null;
  project_id: string | null;
  agent_id: string | null;
  posted_url: string | null;
  posted_at: string | null;
  notes: string | null;
  tags: string[];
  created_at: string;
  updated_at: string | null;
}

export const marketingContent = {
  list: (params?: { status?: string; channel?: string; project_id?: string }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status', params.status);
    if (params?.channel) qs.set('channel', params.channel);
    if (params?.project_id) qs.set('project_id', params.project_id);
    const query = qs.toString();
    return request<MarketingContent[]>(`/api/mkt-content${query ? `?${query}` : ''}`);
  },
  create: (data: Partial<MarketingContent>) =>
    request<MarketingContent>('/api/mkt-content', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<MarketingContent>) =>
    request<MarketingContent>(`/api/mkt-content/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) =>
    request<{ deleted: boolean }>(`/api/mkt-content/${id}`, { method: 'DELETE' }),
};

// --- Brand Profile ---

export interface BrandProfile {
  id: string | null;
  name: string;
  bio: string;
  tone: string;
  social_handles: Record<string, string>;
  topics: string[];
  talking_points: Record<string, unknown>;
  avoid: string[];
  example_posts: Record<string, unknown>[];
  notification_prefs: NotificationPrefs;
  created_at: string | null;
  updated_at: string | null;
}

export interface NotificationPrefs {
  agent_completions: boolean;
  agent_failures: boolean;
  signal_summary: boolean;
  content_drafts: boolean;
}

export const brand = {
  get: () => request<BrandProfile>('/api/brand-profile'),
  update: (data: Partial<BrandProfile>) =>
    request<BrandProfile>('/api/brand-profile', { method: 'PUT', body: JSON.stringify(data) }),
};

// --- Agent Memory ---

export interface AgentMemoryEntry {
  id: string;
  agent_id: string | null;
  key: string;
  value: string;
  memory_type: string;
  created_at: string;
  updated_at: string;
}

export const agentMemory = {
  list: (agentId: string) =>
    request<AgentMemoryEntry[]>(`/api/agents/${agentId}/memory`),
  create: (agentId: string, data: { key: string; value: string; memory_type?: string }) =>
    request<{ id: string; created?: boolean; updated?: boolean }>(`/api/agents/${agentId}/memory`, { method: 'POST', body: JSON.stringify(data) }),
  delete: (agentId: string, key: string) =>
    request<{ deleted: boolean }>(`/api/agents/${agentId}/memory/${encodeURIComponent(key)}`, { method: 'DELETE' }),
};

// --- WebSocket ---

export function connectWebSocket(onMessage: (event: { type: string; data: any }) => void): WebSocket | null {
  const wsUrl = API_BASE.replace(/^http/, 'ws') + '/ws';
  const maxRetries = 10;
  let retryCount = 0;
  const connect = (): WebSocket | null => {
    try {
      const ws = new WebSocket(wsUrl);
      ws.onopen = () => { retryCount = 0; };
      ws.onmessage = (e) => {
        try {
          const parsed = JSON.parse(e.data);
          onMessage(parsed);
        } catch {}
      };
      ws.onclose = () => {
        if (retryCount < maxRetries) {
          const delay = Math.min(1000 * Math.pow(2, retryCount), 30000);
          retryCount++;
          setTimeout(connect, delay);
        }
      };
      return ws;
    } catch {
      return null;
    }
  };
  return connect();
}
