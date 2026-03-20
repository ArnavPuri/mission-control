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
  idea_count: number;
  feedback_count: number;
  content_count: number;
  agent_count: number;
  created_at: string;
}

export interface ProjectHealth {
  project_id: string;
  project_name: string;
  score: number;
  status: 'healthy' | 'needs_attention' | 'at_risk';
  metrics: {
    total_tasks: number;
    done_tasks: number;
    overdue_tasks: number;
    blocked_tasks: number;
    completion_rate: number;
    weekly_velocity: number;
    active_goals: number;
    avg_goal_progress: number;
    monthly_activity: number;
  };
}

export const projects = {
  list: () => request<Project[]>('/api/projects'),
  create: (data: Partial<Project>) => request<{ id: string }>('/api/projects', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Project>) => request<{ updated: boolean }>(`/api/projects/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) => request<{ deleted: boolean }>(`/api/projects/${id}`, { method: 'DELETE' }),
  health: (id: string) => request<ProjectHealth>(`/api/projects/${id}/health`),
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

export const agents = {
  list: () => request<Agent[]>('/api/agents'),
  get: (id: string) => request<AgentDetail>(`/api/agents/${id}`),
  create: (data: Partial<AgentDetail>) => request<AgentDetail>('/api/agents', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<AgentDetail>) => request<AgentDetail>(`/api/agents/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) => request<{ disabled: boolean }>(`/api/agents/${id}`, { method: 'DELETE' }),
  run: (id: string) => request<{ run_id: string; status: string }>(`/api/agents/${id}/run`, { method: 'POST' }),
  dryRun: (id: string) => request<Record<string, unknown>>(`/api/agents/${id}/run?dry_run=true`, { method: 'POST' }),
  stop: (id: string) => request<{ status: string }>(`/api/agents/${id}/stop`, { method: 'POST' }),
  runs: (id: string, limit = 20) => request<AgentRun[]>(`/api/agents/${id}/runs?limit=${limit}`),
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

// --- Agent Analytics ---

export interface AgentAnalyticsOverview {
  days: number;
  agents: {
    agent_id: string;
    agent_name: string;
    agent_slug: string;
    model: string;
    total_runs: number;
    completed: number;
    failed: number;
    success_rate: number;
    total_cost_usd: number;
    total_tokens: number;
    avg_cost_per_run: number;
    avg_duration_seconds: number;
    daily_costs: Record<string, number>;
    last_run_at: string | null;
  }[];
  totals: {
    total_agents: number;
    total_runs: number;
    total_completed: number;
    total_failed: number;
    overall_success_rate: number;
    total_cost_usd: number;
  };
}

export const agentAnalytics = {
  overview: (days = 30) => request<AgentAnalyticsOverview>(`/api/analytics/agents/overview?days=${days}`),
};

// --- Triggers ---

export interface AgentTrigger {
  id: string;
  agent_id: string;
  agent_name: string | null;
  name: string;
  description: string;
  is_active: boolean;
  entity_type: string;
  event: string;
  condition: Record<string, string> | null;
  last_triggered_at: string | null;
  trigger_count: number;
  created_at: string;
}

export const triggers = {
  list: () => request<AgentTrigger[]>('/api/triggers'),
  create: (data: Partial<AgentTrigger>) => request<{ id: string }>('/api/triggers', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<AgentTrigger>) => request<{ updated: boolean }>(`/api/triggers/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) => request<{ deleted: boolean }>(`/api/triggers/${id}`, { method: 'DELETE' }),
};

// --- Auto-tag ---

export const autotag = {
  task: (id: string) => request<{ tags: string[] }>(`/api/autotag/task/${id}`, { method: 'POST' }),
  idea: (id: string) => request<{ tags: string[] }>(`/api/autotag/idea/${id}`, { method: 'POST' }),
  batch: (entityType: string, limit = 10) => request<{ tagged: number }>(`/api/autotag/batch?entity_type=${entityType}&limit=${limit}`, { method: 'POST' }),
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
  get: (id: string) => request<Note>(`/api/notes/${id}`),
  create: (data: Partial<Note>) => request<{ id: string }>('/api/notes', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Note>) => request<{ updated: boolean }>(`/api/notes/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) => request<{ deleted: boolean }>(`/api/notes/${id}`, { method: 'DELETE' }),
};

// --- API Keys ---

export interface ApiKeyRecord {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  is_active: boolean;
  last_used_at?: string;
  expires_at?: string;
  created_at: string;
}

export const apiKeys = {
  list: () => request<ApiKeyRecord[]>('/api/keys'),
  create: (data: { name: string; scopes?: string[] }) => request<{ id: string; key: string; message: string }>('/api/keys', { method: 'POST', body: JSON.stringify(data) }),
  revoke: (id: string) => request<{ revoked: boolean }>(`/api/keys/${id}`, { method: 'DELETE' }),
};

// --- GitHub Repos ---

export interface GitHubRepo {
  id: string;
  owner: string;
  repo: string;
  full_name: string;
  is_active: boolean;
  sync_issues: boolean;
  sync_prs: boolean;
  auto_create_tasks: boolean;
  project_id?: string;
  last_synced_at?: string;
  created_at: string;
}

export const github = {
  repos: () => request<GitHubRepo[]>('/api/github'),
  addRepo: (data: { owner: string; repo: string; auto_create_tasks?: boolean; project_id?: string }) =>
    request<{ id: string; webhook_secret: string; webhook_url: string }>('/api/github', { method: 'POST', body: JSON.stringify(data) }),
  updateRepo: (id: string, data: Partial<GitHubRepo>) => request<{ updated: boolean }>(`/api/github/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  removeRepo: (id: string) => request<{ deleted: boolean }>(`/api/github/${id}`, { method: 'DELETE' }),
};

// --- RSS Feeds ---

export interface RSSFeed {
  id: string;
  title: string;
  url: string;
  is_active: boolean;
  tags: string[];
  fetch_interval_minutes: number;
  last_fetched_at?: string;
  error_count: number;
  last_error?: string;
  created_at: string;
}

export const feeds = {
  list: () => request<RSSFeed[]>('/api/feeds'),
  create: (data: { title: string; url: string; tags?: string[] }) => request<{ id: string }>('/api/feeds', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<RSSFeed>) => request<{ updated: boolean }>(`/api/feeds/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) => request<{ deleted: boolean }>(`/api/feeds/${id}`, { method: 'DELETE' }),
  fetch: (id: string) => request<{ imported: number }>(`/api/feeds/${id}/fetch`, { method: 'POST' }),
};

// --- Workflows ---

export interface WorkflowStep {
  id: string;
  agent_id: string;
  agent_name: string | null;
  name: string;
  sort_order: number;
  depends_on: string[];
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  config: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  run_id: string | null;
  error: string | null;
}

export interface Workflow {
  id: string;
  name: string;
  description: string;
  status: 'draft' | 'active' | 'running' | 'completed' | 'failed' | 'paused';
  trigger_type: string;
  trigger_value: string | null;
  steps: WorkflowStep[];
  created_at: string;
  updated_at: string | null;
}

export const workflows = {
  list: () => request<Workflow[]>('/api/workflows'),
  get: (id: string) => request<Workflow>(`/api/workflows/${id}`),
  create: (data: { name: string; description?: string; steps?: { agent_id: string; name: string; sort_order?: number; depends_on?: string[] }[] }) =>
    request<Workflow>('/api/workflows', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Workflow>) =>
    request<{ updated: boolean }>(`/api/workflows/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) => request<{ deleted: boolean }>(`/api/workflows/${id}`, { method: 'DELETE' }),
  addStep: (workflowId: string, data: { agent_id: string; name: string; sort_order?: number; depends_on?: string[] }) =>
    request<{ id: string }>(`/api/workflows/${workflowId}/steps`, { method: 'POST', body: JSON.stringify(data) }),
  removeStep: (workflowId: string, stepId: string) =>
    request<{ deleted: boolean }>(`/api/workflows/${workflowId}/steps/${stepId}`, { method: 'DELETE' }),
  run: (id: string) => request<{ id: string; status: string; steps: number }>(`/api/workflows/${id}/run`, { method: 'POST' }),
};

// --- Smart Priority ---

export interface PrioritySuggestion {
  suggested_priority: string;
  confidence: number;
  scores: Record<string, number>;
  reasons: string[];
}

export const smartPriority = {
  suggest: (text: string) =>
    request<PrioritySuggestion>('/api/priority/suggest', { method: 'POST', body: JSON.stringify({ text }) }),
  bulkSuggest: () =>
    request<{ suggestions: (PrioritySuggestion & { task_id: string; text: string; current_priority: string })[]; total_evaluated: number }>('/api/priority/bulk-suggest', { method: 'POST' }),
};

// --- Push Notifications ---

export const push = {
  subscribe: (subscription: { endpoint: string; keys: { p256dh: string; auth: string } }) =>
    request<{ id: string; subscribed: boolean }>('/api/push/subscribe', { method: 'POST', body: JSON.stringify(subscription) }),
  unsubscribe: (id: string) =>
    request<{ unsubscribed: boolean }>(`/api/push/subscribe/${id}`, { method: 'DELETE' }),
  send: (data: { title: string; body?: string; category?: string }) =>
    request<{ sent: number }>('/api/push/send', { method: 'POST', body: JSON.stringify(data) }),
};

// --- Task Reorder ---

export const taskReorder = {
  reorder: (taskIds: string[]) =>
    request<{ reordered: number }>('/api/tasks/reorder', { method: 'POST', body: JSON.stringify({ task_ids: taskIds }) }),
};

// --- Routines ---

export interface RoutineItem {
  id: string;
  text: string;
  sort_order: number;
  duration_minutes?: number;
}

export interface Routine {
  id: string;
  name: string;
  description: string;
  routine_type: 'morning' | 'evening' | 'custom';
  is_active: boolean;
  days: string[];
  items: RoutineItem[];
  created_at: string;
  updated_at: string | null;
}

export interface RoutineCompletion {
  id: string;
  completed_items: string[];
  total_items: number;
  completed_at: string;
}

export const routines = {
  list: (activeOnly = true, routineType?: string) => {
    const qs = new URLSearchParams({ active_only: String(activeOnly) });
    if (routineType) qs.set('routine_type', routineType);
    return request<Routine[]>(`/api/routines?${qs}`);
  },
  get: (id: string) => request<Routine>(`/api/routines/${id}`),
  create: (data: Partial<Routine> & { items?: { text: string; sort_order?: number; duration_minutes?: number }[] }) =>
    request<Routine>('/api/routines', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<Routine>) =>
    request<{ updated: boolean }>(`/api/routines/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) => request<{ deleted: boolean }>(`/api/routines/${id}`, { method: 'DELETE' }),
  addItem: (routineId: string, data: { text: string; sort_order?: number; duration_minutes?: number }) =>
    request<{ id: string }>(`/api/routines/${routineId}/items`, { method: 'POST', body: JSON.stringify(data) }),
  updateItem: (routineId: string, itemId: string, data: Partial<RoutineItem>) =>
    request<{ updated: boolean }>(`/api/routines/${routineId}/items/${itemId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteItem: (routineId: string, itemId: string) =>
    request<{ deleted: boolean }>(`/api/routines/${routineId}/items/${itemId}`, { method: 'DELETE' }),
  complete: (routineId: string, completedItems: string[]) =>
    request<{ id: string; completed: number; total: number }>(`/api/routines/${routineId}/complete`, { method: 'POST', body: JSON.stringify({ completed_items: completedItems }) }),
  completions: (routineId: string, limit = 30) =>
    request<RoutineCompletion[]>(`/api/routines/${routineId}/completions?limit=${limit}`),
};

// --- Deduplication ---

export interface DuplicateMatch {
  id: string;
  text: string;
  similarity: number;
  entity_type: string;
}

export interface DuplicateGroup {
  items: { id: string; text: string; status?: string; score?: number; created_at: string }[];
  similarity: number;
}

export const dedup = {
  tasks: (threshold = 0.7) => request<{ entity_type: string; threshold: number; groups: DuplicateGroup[] }>(`/api/dedup/tasks?threshold=${threshold}`),
  ideas: (threshold = 0.7) => request<{ entity_type: string; threshold: number; groups: DuplicateGroup[] }>(`/api/dedup/ideas?threshold=${threshold}`),
  check: (text: string, entityType = 'task') =>
    request<{ text: string; is_duplicate: boolean; matches: DuplicateMatch[] }>('/api/dedup/check', { method: 'POST', body: JSON.stringify({ text, entity_type: entityType }) }),
};

// --- User Patterns ---

export const patterns = {
  activityPatterns: (days = 30) => request<Record<string, unknown>>(`/api/patterns/activity-patterns?days=${days}`),
  scheduleSuggestions: () => request<Record<string, unknown>>('/api/patterns/schedule-suggestions'),
};

// --- Webhook Templates ---

export const webhookTemplates = {
  list: () => request<Array<Record<string, unknown>>>('/api/webhooks/templates/templates'),
  get: (id: string) => request<Record<string, unknown>>(`/api/webhooks/templates/templates/${id}`),
  create: (data: { template_id: string; url?: string; secret?: string; events?: string[] }) =>
    request<Record<string, unknown>>('/api/webhooks/templates/templates/create', { method: 'POST', body: JSON.stringify(data) }),
};

// --- Rate Limit ---

export const rateLimit = {
  usage: (key?: string) => request<Record<string, unknown>>(`/api/rate-limit/usage${key ? `?key=${key}` : ''}`),
  limits: () => request<Record<string, unknown>>('/api/rate-limit/limits'),
};

// --- Agent Versions ---

export const agentVersions = {
  list: (agentId: string) => request<Record<string, unknown>>(`/api/agents/${agentId}/versions`),
  get: (agentId: string, version: number) => request<Record<string, unknown>>(`/api/agents/${agentId}/versions/${version}`),
  diff: (agentId: string, v1: number, v2: number) => request<Record<string, unknown>>(`/api/agents/${agentId}/versions/${v1}/diff/${v2}`),
  snapshot: (agentId: string) => request<Record<string, unknown>>(`/api/agents/${agentId}/snapshot`, { method: 'POST' }),
};

// --- Agent Marketplace ---

export const marketplace = {
  categories: () => request<Array<Record<string, unknown>>>('/api/marketplace/categories'),
  gallery: (params?: { category?: string; search?: string; installed_only?: boolean }) => {
    const qs = new URLSearchParams();
    if (params?.category) qs.set('category', params.category);
    if (params?.search) qs.set('search', params.search);
    if (params?.installed_only) qs.set('installed_only', 'true');
    return request<Array<Record<string, unknown>>>(`/api/marketplace/gallery?${qs}`);
  },
  install: (skill_file: string) => request<Record<string, unknown>>('/api/marketplace/install', { method: 'POST', body: JSON.stringify({ skill_file }) }),
  rate: (agent_id: string, rating: number, comment?: string) => request<Record<string, unknown>>('/api/marketplace/rate', { method: 'POST', body: JSON.stringify({ agent_id, rating, comment }) }),
  stats: () => request<Record<string, unknown>>('/api/marketplace/stats'),
};

// --- Pipeline Builder ---

export const pipelines = {
  list: () => request<Array<Record<string, unknown>>>('/api/pipelines'),
  create: (data: { name: string; description?: string; steps: Array<{ agent_id: string; name: string; depends_on?: string[] }> }) =>
    request<Record<string, unknown>>('/api/pipelines', { method: 'POST', body: JSON.stringify(data) }),
  preview: (id: string) => request<Record<string, unknown>>(`/api/pipelines/${id}/preview`),
  addStep: (id: string, step: { agent_id: string; name: string; depends_on?: string[] }) =>
    request<Record<string, unknown>>(`/api/pipelines/${id}/add-step`, { method: 'POST', body: JSON.stringify(step) }),
  removeStep: (pipelineId: string, stepId: string) =>
    request<Record<string, unknown>>(`/api/pipelines/${pipelineId}/steps/${stepId}`, { method: 'DELETE' }),
};

// --- A/B Testing ---

export const abTests = {
  list: () => request<Array<Record<string, unknown>>>('/api/ab-tests'),
  create: (data: { agent_id: string; name: string; variants: Array<{ name: string; prompt_template: string; weight?: number }> }) =>
    request<Record<string, unknown>>('/api/ab-tests', { method: 'POST', body: JSON.stringify(data) }),
  results: (agentId: string) => request<Record<string, unknown>>(`/api/ab-tests/${agentId}/results`),
  update: (agentId: string, testName: string, data: { is_active?: boolean; winner?: string }) =>
    request<Record<string, unknown>>(`/api/ab-tests/${agentId}/tests/${testName}`, { method: 'PATCH', body: JSON.stringify(data) }),
};

// --- Agent Budget ---

export const agentBudget = {
  overview: () => request<Record<string, unknown>>('/api/budget/overview'),
  spending: (agentId: string, days?: number) => request<Record<string, unknown>>(`/api/budget/${agentId}/spending?days=${days || 30}`),
  setLimits: (agentId: string, limits: { daily_limit_usd?: number; weekly_limit_usd?: number; monthly_limit_usd?: number }) =>
    request<Record<string, unknown>>(`/api/budget/${agentId}/limits`, { method: 'PATCH', body: JSON.stringify(limits) }),
};

// --- Backup ---

export const backup = {
  create: () => request<Record<string, unknown>>('/api/backup/backup'),
  summary: () => request<{ total_rows: number; tables: Record<string, number> }>('/api/backup/backup/summary'),
  downloadUrl: () => `${API_BASE}/api/backup/backup`,
};

// --- Reading Summarize ---

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

export function fetchSignals(params?: { status?: string; source_type?: string; signal_type?: string; project_id?: string }) {
  const qs = new URLSearchParams();
  if (params?.status) qs.set('status', params.status);
  if (params?.source_type) qs.set('source_type', params.source_type);
  if (params?.signal_type) qs.set('signal_type', params.signal_type);
  if (params?.project_id) qs.set('project_id', params.project_id);
  const query = qs.toString();
  return request<MarketingSignal[]>(`/api/mkt-signals${query ? `?${query}` : ''}`);
}

export function createSignal(data: Partial<MarketingSignal>) {
  return request<MarketingSignal>('/api/mkt-signals', { method: 'POST', body: JSON.stringify(data) });
}

export function updateSignal(id: string, data: Partial<MarketingSignal>) {
  return request<MarketingSignal>(`/api/mkt-signals/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
}

export function deleteSignal(id: string) {
  return request<{ deleted: boolean }>(`/api/mkt-signals/${id}`, { method: 'DELETE' });
}

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

export function fetchContent(params?: { status?: string; channel?: string; project_id?: string }) {
  const qs = new URLSearchParams();
  if (params?.status) qs.set('status', params.status);
  if (params?.channel) qs.set('channel', params.channel);
  if (params?.project_id) qs.set('project_id', params.project_id);
  const query = qs.toString();
  return request<MarketingContent[]>(`/api/mkt-content${query ? `?${query}` : ''}`);
}

export function createContent(data: Partial<MarketingContent>) {
  return request<MarketingContent>('/api/mkt-content', { method: 'POST', body: JSON.stringify(data) });
}

export function updateContent(id: string, data: Partial<MarketingContent>) {
  return request<MarketingContent>(`/api/mkt-content/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
}

export function deleteContent(id: string) {
  return request<{ deleted: boolean }>(`/api/mkt-content/${id}`, { method: 'DELETE' });
}

export function fetchMarketingStats() {
  return request<{
    signals: { by_status: Record<string, number>; by_type: Record<string, number>; total: number };
    content: { by_status: Record<string, number>; by_channel: Record<string, number>; total: number };
  }>('/api/mkt-stats');
}

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

// --- Notification Preferences ---

export interface NotificationPrefs {
  agent_completions: boolean;
  agent_failures: boolean;
  signal_summary: boolean;
  content_drafts: boolean;
}

export function getNotificationPrefs() {
  return request<NotificationPrefs>('/api/brand-profile/notification-prefs');
}

export function updateNotificationPrefs(data: Partial<NotificationPrefs>) {
  return request<NotificationPrefs>('/api/brand-profile/notification-prefs', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}
