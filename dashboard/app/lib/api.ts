/**
 * Mission Control API Client
 *
 * Connects the dashboard to the FastAPI backend.
 * All data flows through here — the dashboard never
 * touches the database directly.
 */

// Empty = same origin: in Docker, Caddy serves the dashboard and proxies /api,
// /health and /ws to the backend. `npm run dev` sets it via .env.development.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

/** Thrown when the session is missing or expired; the app redirects to /login. */
export class UnauthorizedError extends Error {}

function goToLogin() {
  if (typeof window === 'undefined' || window.location.pathname.startsWith('/login')) return;
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.href = `/login?next=${next}`;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    ...options,
  });
  if (res.status === 401 && !path.startsWith('/api/auth/')) {
    goToLogin();
    throw new UnauthorizedError('Not signed in');
  }
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
  github_repo?: string | null;
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

export type Recurrence = 'daily' | 'weekdays' | 'weekly' | 'monthly';

export interface Task {
  id: string;
  text: string;
  description?: string | null;
  url?: string | null;
  status: 'todo' | 'in_progress' | 'blocked' | 'done';
  priority: 'critical' | 'high' | 'medium' | 'low';
  project_id?: string | null;
  project_name?: string | null;
  project_has_repo?: boolean;
  /** URL of the GitHub issue when this is a dev task handed to Claude Code */
  github_issue?: string | null;
  assigned_agent_id?: string | null;
  assigned_agent_name?: string | null;
  /** Set when an agent handed this off from another task */
  parent_task_id?: string | null;
  source: string;
  tags: string[];
  /** End of the day it's due (overdue once that day is over) */
  due_date?: string | null;
  /** When to send a Telegram reminder; reminded_at is when one was last sent */
  remind_at?: string | null;
  reminded_at?: string | null;
  /** Completing a repeating task creates the next one */
  recurrence?: Recurrence | null;
  completed_at?: string | null;
  created_at: string;
}

export interface TaskComment {
  id: string;
  /** "user", "system" or "agent:<slug>" */
  author: string;
  body: string;
  run_id: string | null;
  created_at: string;
}

export interface TaskHandoff {
  id: string;
  text: string;
  status: Task['status'];
  assigned_agent_name: string | null;
}

export interface TaskDetail extends Task {
  agent_running: boolean;
  /** What the agent is doing right now, oldest first ("Searching the web: …") */
  progress?: string[];
  /** The task this was handed off from */
  parent?: { id: string; text: string } | null;
  /** Tasks the agent handed to teammates while working on this one */
  handoffs?: TaskHandoff[];
  comments: TaskComment[];
}

export const tasks = {
  list: (params?: { status?: string; project_id?: string; tag?: string }) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    return request<Task[]>(`/api/tasks${qs ? '?' + qs : ''}`);
  },
  create: (data: Partial<Task>) => request<{ id: string }>('/api/tasks', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Task>) => request<{ updated: boolean; next_id: string | null }>(`/api/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) => request<{ deleted: boolean }>(`/api/tasks/${id}`, { method: 'DELETE' }),
  get: (id: string) => request<TaskDetail>(`/api/tasks/${id}`),
  /** Assign to an agent (it starts working right away), or pass null to unassign. */
  assign: (id: string, agentId: string | null, note?: string) =>
    request<{ assigned: string | null; started?: boolean }>(`/api/tasks/${id}/assign`, {
      method: 'POST', body: JSON.stringify({ agent_id: agentId, note }),
    }),
  /** Open a GitHub issue for this task in its project's repo (for Claude Code). */
  sendToGitHub: (id: string) => request<{ issue_url: string }>(`/api/tasks/${id}/github`, { method: 'POST' }),
  comment: (id: string, body: string) =>
    request<{ added: boolean; agent: string | null }>(`/api/tasks/${id}/comments`, {
      method: 'POST', body: JSON.stringify({ body }),
    }),
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

export interface AgentAnalytics {
  days: number;
  totals: { total_runs: number; overall_success_rate: number; total_cost_usd: number };
  agents: {
    agent_id: string;
    total_runs: number;
    success_rate: number;
    total_cost_usd: number;
    daily_costs: Record<string, number>;
  }[];
}

export const agents = {
  list: () => request<Agent[]>('/api/agents'),
  get: (id: string) => request<AgentDetail>(`/api/agents/${id}`),
  create: (data: Partial<AgentDetail>) => request<AgentDetail>('/api/agents', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<AgentDetail>) => request<AgentDetail>(`/api/agents/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  triggerRun: (id: string) => request<{ status: string }>(`/api/agents/${id}/run`, { method: 'POST' }),
  run: (id: string) => request<{ status: string }>(`/api/agents/${id}/run`, { method: 'POST' }),
  stop: (id: string) => request<{ status: string }>(`/api/agents/${id}/stop`, { method: 'POST' }),
  dryRun: (id: string) => request<Record<string, unknown>>(`/api/agents/${id}/run?dry_run=true`, { method: 'POST' }),
  runs: (id: string, limit = 20) => request<AgentRun[]>(`/api/agents/${id}/runs?limit=${limit}`),
  analytics: (days = 30) => request<AgentAnalytics>(`/api/agents/analytics?days=${days}`),
  runDetail: (agentId: string, runId: string) => request<RunDetailResponse>(`/api/agents/${agentId}/runs/${runId}`),
  expandPrompt: (data: { description: string; agent_type?: string; data_reads?: string[]; data_writes?: string[] }) =>
    request<{ prompt: string }>('/api/agents/expand-prompt', { method: 'POST', body: JSON.stringify(data) }),
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

// --- Marketing Content ---

export interface MarketingContent {
  id: string;
  title: string;
  body: string;
  channel: string;
  status: 'draft' | 'approved' | 'posted' | 'archived';
  source: string;
  task_id: string | null;
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

// --- Auth ---

export interface AuthState {
  auth_enabled: boolean;
  authenticated: boolean;
}

export const auth = {
  me: () => request<AuthState>('/api/auth/me'),
  login: (password: string) => request<AuthState>('/api/auth/login', { method: 'POST', body: JSON.stringify({ password }) }),
  logout: () => request<AuthState>('/api/auth/logout', { method: 'POST' }),
};

// --- System & Activity ---

export interface Health {
  status: string;
  database: string;
  llm: string;
  telegram: string;
  github?: string;
}

export interface ActivityItem {
  id: string;
  /** "user", "system" or "agent:<slug>" */
  author: string;
  author_name: string;
  body: string;
  created_at: string;
  task: { id: string; text: string; status: Task['status'] };
}

export const system = {
  health: () => request<Health>('/health'),
};

export const activity = {
  list: (limit = 20) => request<ActivityItem[]>(`/api/activity?limit=${limit}`),
};

// --- WebSocket ---

export function connectWebSocket(onMessage: (event: { type: string; data: any }) => void): WebSocket | null {
  const base = API_BASE || window.location.origin;
  const wsUrl = base.replace(/^http/, 'ws') + '/ws';
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
      ws.onclose = (e) => {
        if (e.code === 4401) return; // not signed in; the login redirect takes over
        // Keep retrying (capped backoff) so live updates survive backend restarts
        const delay = Math.min(1000 * Math.pow(2, retryCount), 30000);
        retryCount++;
        setTimeout(connect, delay);
      };
      return ws;
    } catch {
      return null;
    }
  };
  return connect();
}
