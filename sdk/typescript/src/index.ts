/**
 * Mission Control TypeScript SDK
 *
 * Thin fetch wrapper for the Mission Control REST API.
 *
 * @example
 * ```ts
 * import { MissionControl } from '@mission-control/sdk';
 * const mc = new MissionControl({ baseUrl: 'http://localhost:8000', apiKey: 'mc_...' });
 * const tasks = await mc.tasks.list();
 * await mc.tasks.create({ text: 'Buy groceries', priority: 'high' });
 * ```
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MissionControlConfig {
  baseUrl?: string;
  apiKey?: string;
  timeout?: number;
}

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

export interface Idea {
  id: string;
  text: string;
  tags: string[];
  source: string;
  score?: number;
  project_id?: string;
  created_at: string;
}

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

export interface Agent {
  id: string;
  name: string;
  slug: string;
  description: string;
  agent_type: string;
  status: 'idle' | 'running' | 'error' | 'disabled';
  model: string;
  last_run_at?: string;
}

export interface SearchResponse {
  query: string;
  total: number;
  results: Array<{
    type: string;
    id: string;
    title: string;
    status?: string;
    priority?: string;
    tags?: string[];
    created_at: string;
  }>;
}

// ---------------------------------------------------------------------------
// HTTP helper
// ---------------------------------------------------------------------------

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API error ${status}: ${detail}`);
    this.name = 'ApiError';
  }
}

async function request<T>(
  baseUrl: string,
  method: string,
  path: string,
  options: {
    headers: Record<string, string>;
    params?: Record<string, string>;
    body?: unknown;
    timeout?: number;
  },
): Promise<T> {
  const url = new URL(path, baseUrl);
  if (options.params) {
    for (const [k, v] of Object.entries(options.params)) {
      if (v !== undefined && v !== null) url.searchParams.set(k, v);
    }
  }

  const controller = new AbortController();
  const timeoutId = options.timeout
    ? setTimeout(() => controller.abort(), options.timeout)
    : undefined;

  try {
    const res = await fetch(url.toString(), {
      method,
      headers: options.headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(res.status, err.detail || `HTTP ${res.status}`);
    }

    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

// ---------------------------------------------------------------------------
// Resource classes
// ---------------------------------------------------------------------------

class TasksResource {
  constructor(
    private baseUrl: string,
    private headers: Record<string, string>,
    private timeout: number,
  ) {}

  async list(params?: { status?: string; project_id?: string }): Promise<Task[]> {
    const p: Record<string, string> = {};
    if (params?.status) p.status = params.status;
    if (params?.project_id) p.project_id = params.project_id;
    return request(this.baseUrl, 'GET', '/api/tasks', { headers: this.headers, params: p, timeout: this.timeout });
  }

  async get(id: string): Promise<Task> {
    return request(this.baseUrl, 'GET', `/api/tasks/${id}`, { headers: this.headers, timeout: this.timeout });
  }

  async create(data: Partial<Task>): Promise<{ id: string }> {
    return request(this.baseUrl, 'POST', '/api/tasks', { headers: this.headers, body: data, timeout: this.timeout });
  }

  async update(id: string, data: Partial<Task>): Promise<{ updated: boolean }> {
    return request(this.baseUrl, 'PATCH', `/api/tasks/${id}`, { headers: this.headers, body: data, timeout: this.timeout });
  }

  async delete(id: string): Promise<{ deleted: boolean }> {
    return request(this.baseUrl, 'DELETE', `/api/tasks/${id}`, { headers: this.headers, timeout: this.timeout });
  }

  async reorder(taskIds: string[]): Promise<{ reordered: number }> {
    return request(this.baseUrl, 'POST', '/api/tasks/reorder', { headers: this.headers, body: { task_ids: taskIds }, timeout: this.timeout });
  }
}

class IdeasResource {
  constructor(
    private baseUrl: string,
    private headers: Record<string, string>,
    private timeout: number,
  ) {}

  async list(): Promise<Idea[]> {
    return request(this.baseUrl, 'GET', '/api/ideas', { headers: this.headers, timeout: this.timeout });
  }

  async get(id: string): Promise<Idea> {
    return request(this.baseUrl, 'GET', `/api/ideas/${id}`, { headers: this.headers, timeout: this.timeout });
  }

  async create(data: Partial<Idea>): Promise<{ id: string }> {
    return request(this.baseUrl, 'POST', '/api/ideas', { headers: this.headers, body: data, timeout: this.timeout });
  }

  async update(id: string, data: Partial<Idea>): Promise<{ updated: boolean }> {
    return request(this.baseUrl, 'PATCH', `/api/ideas/${id}`, { headers: this.headers, body: data, timeout: this.timeout });
  }

  async delete(id: string): Promise<{ deleted: boolean }> {
    return request(this.baseUrl, 'DELETE', `/api/ideas/${id}`, { headers: this.headers, timeout: this.timeout });
  }
}

class NotesResource {
  constructor(
    private baseUrl: string,
    private headers: Record<string, string>,
    private timeout: number,
  ) {}

  async list(params?: { tag?: string }): Promise<Note[]> {
    const p: Record<string, string> = {};
    if (params?.tag) p.tag = params.tag;
    return request(this.baseUrl, 'GET', '/api/notes', { headers: this.headers, params: p, timeout: this.timeout });
  }

  async get(id: string): Promise<Note> {
    return request(this.baseUrl, 'GET', `/api/notes/${id}`, { headers: this.headers, timeout: this.timeout });
  }

  async create(data: Partial<Note>): Promise<{ id: string }> {
    return request(this.baseUrl, 'POST', '/api/notes', { headers: this.headers, body: data, timeout: this.timeout });
  }

  async update(id: string, data: Partial<Note>): Promise<{ updated: boolean }> {
    return request(this.baseUrl, 'PATCH', `/api/notes/${id}`, { headers: this.headers, body: data, timeout: this.timeout });
  }

  async delete(id: string): Promise<{ deleted: boolean }> {
    return request(this.baseUrl, 'DELETE', `/api/notes/${id}`, { headers: this.headers, timeout: this.timeout });
  }
}

class ProjectsResource {
  constructor(
    private baseUrl: string,
    private headers: Record<string, string>,
    private timeout: number,
  ) {}

  async list(): Promise<Project[]> {
    return request(this.baseUrl, 'GET', '/api/projects', { headers: this.headers, timeout: this.timeout });
  }

  async get(id: string): Promise<Project> {
    return request(this.baseUrl, 'GET', `/api/projects/${id}`, { headers: this.headers, timeout: this.timeout });
  }

  async create(data: Partial<Project>): Promise<{ id: string }> {
    return request(this.baseUrl, 'POST', '/api/projects', { headers: this.headers, body: data, timeout: this.timeout });
  }

  async update(id: string, data: Partial<Project>): Promise<{ updated: boolean }> {
    return request(this.baseUrl, 'PATCH', `/api/projects/${id}`, { headers: this.headers, body: data, timeout: this.timeout });
  }

  async delete(id: string): Promise<{ deleted: boolean }> {
    return request(this.baseUrl, 'DELETE', `/api/projects/${id}`, { headers: this.headers, timeout: this.timeout });
  }

  async health(id: string): Promise<Record<string, unknown>> {
    return request(this.baseUrl, 'GET', `/api/projects/${id}/health`, { headers: this.headers, timeout: this.timeout });
  }
}

class AgentsResource {
  constructor(
    private baseUrl: string,
    private headers: Record<string, string>,
    private timeout: number,
  ) {}

  async list(): Promise<Agent[]> {
    return request(this.baseUrl, 'GET', '/api/agents', { headers: this.headers, timeout: this.timeout });
  }

  async get(id: string): Promise<Agent> {
    return request(this.baseUrl, 'GET', `/api/agents/${id}`, { headers: this.headers, timeout: this.timeout });
  }

  async create(data: Partial<Agent>): Promise<Agent> {
    return request(this.baseUrl, 'POST', '/api/agents', { headers: this.headers, body: data, timeout: this.timeout });
  }

  async update(id: string, data: Partial<Agent>): Promise<Agent> {
    return request(this.baseUrl, 'PATCH', `/api/agents/${id}`, { headers: this.headers, body: data, timeout: this.timeout });
  }

  async delete(id: string): Promise<{ disabled: boolean }> {
    return request(this.baseUrl, 'DELETE', `/api/agents/${id}`, { headers: this.headers, timeout: this.timeout });
  }

  async run(idOrSlug: string, options?: { dryRun?: boolean }): Promise<{ run_id: string; status: string }> {
    const p: Record<string, string> = {};
    if (options?.dryRun) p.dry_run = 'true';
    return request(this.baseUrl, 'POST', `/api/agents/${idOrSlug}/run`, { headers: this.headers, params: p, timeout: this.timeout });
  }

  async stop(id: string): Promise<{ status: string }> {
    return request(this.baseUrl, 'POST', `/api/agents/${id}/stop`, { headers: this.headers, timeout: this.timeout });
  }

  async runs(id: string, limit = 20): Promise<Array<Record<string, unknown>>> {
    return request(this.baseUrl, 'GET', `/api/agents/${id}/runs`, { headers: this.headers, params: { limit: String(limit) }, timeout: this.timeout });
  }
}

class SearchResource {
  constructor(
    private baseUrl: string,
    private headers: Record<string, string>,
    private timeout: number,
  ) {}

  async query(q: string, options?: { entityTypes?: string; limit?: number }): Promise<SearchResponse> {
    return request(this.baseUrl, 'GET', '/api/search', {
      headers: this.headers,
      params: {
        q,
        entity_types: options?.entityTypes ?? 'all',
        limit: String(options?.limit ?? 20),
      },
      timeout: this.timeout,
    });
  }
}

// ---------------------------------------------------------------------------
// Main client
// ---------------------------------------------------------------------------

export class MissionControl {
  public readonly tasks: TasksResource;
  public readonly ideas: IdeasResource;
  public readonly notes: NotesResource;
  public readonly projects: ProjectsResource;
  public readonly agents: AgentsResource;
  public readonly search: SearchResource;

  private baseUrl: string;

  constructor(config: MissionControlConfig = {}) {
    this.baseUrl = (config.baseUrl ?? 'http://localhost:8000').replace(/\/+$/, '');
    const timeout = config.timeout ?? 30_000;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (config.apiKey) {
      headers['Authorization'] = `Bearer ${config.apiKey}`;
    }

    this.tasks = new TasksResource(this.baseUrl, headers, timeout);
    this.ideas = new IdeasResource(this.baseUrl, headers, timeout);
    this.notes = new NotesResource(this.baseUrl, headers, timeout);
    this.projects = new ProjectsResource(this.baseUrl, headers, timeout);
    this.agents = new AgentsResource(this.baseUrl, headers, timeout);
    this.search = new SearchResource(this.baseUrl, headers, timeout);
  }
}

export { ApiError };
export default MissionControl;
