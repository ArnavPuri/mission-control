'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import * as api from '../lib/api';
import { subscribe } from '../lib/live';

interface Workspace {
  loaded: boolean;
  tasks: api.Task[];
  projects: api.Project[];
  agents: api.Agent[];
  approvals: api.Approval[];
  content: api.MarketingContent[];
  health: api.Health | null;
  /** Bumps on every backend event; open views use it to refetch their own data. */
  tick: number;
  refresh: () => Promise<void>;
  openTask: (id: string) => void;
  openProject: (project: api.Project) => void;
  openCommandMenu: () => void;
}

const WorkspaceContext = createContext<Workspace | null>(null);

export function useWorkspace(): Workspace {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error('useWorkspace must be used inside <WorkspaceProvider>');
  return ctx;
}

/**
 * Shared data for the shell and pages: tasks, projects, agents, review items.
 * Refreshes whenever the backend broadcasts an event (debounced).
 */
export function WorkspaceProvider({ children, onOpenTask, onOpenProject, onOpenCommandMenu }: {
  children: React.ReactNode;
  onOpenTask: (id: string) => void;
  onOpenProject: (project: api.Project) => void;
  onOpenCommandMenu: () => void;
}) {
  const [loaded, setLoaded] = useState(false);
  const [tasks, setTasks] = useState<api.Task[]>([]);
  const [projects, setProjects] = useState<api.Project[]>([]);
  const [agents, setAgents] = useState<api.Agent[]>([]);
  const [approvals, setApprovals] = useState<api.Approval[]>([]);
  const [content, setContent] = useState<api.MarketingContent[]>([]);
  const [health, setHealth] = useState<api.Health | null>(null);
  const [tick, setTick] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(async () => {
    const results = await Promise.allSettled([
      api.tasks.list(), api.projects.list(), api.agents.list(),
      api.approvals.list(), api.marketingContent.list(),
      api.system.health(),
    ]);
    const [t, p, a, ap, c, h] = results;
    if (t.status === 'fulfilled') setTasks(t.value);
    if (p.status === 'fulfilled') setProjects(p.value);
    if (a.status === 'fulfilled') setAgents(a.value);
    if (ap.status === 'fulfilled') setApprovals(ap.value);
    if (c.status === 'fulfilled') setContent(c.value);
    setHealth(h.status === 'fulfilled' ? h.value : null);
    setLoaded(true);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => subscribe((event) => {
    if (!/^(task|note|content|agent|approval|notification|signal)\./.test(event.type)) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      refresh();
      setTick((n) => n + 1);
    }, 250);
  }), [refresh]);

  // Agents can finish while no event reaches us (e.g. socket reconnecting); poll gently
  useEffect(() => {
    const i = setInterval(refresh, 30000);
    return () => clearInterval(i);
  }, [refresh]);

  const value = useMemo<Workspace>(() => ({
    loaded, tasks, projects, agents, approvals, content, health, tick, refresh,
    openTask: onOpenTask, openProject: onOpenProject, openCommandMenu: onOpenCommandMenu,
  }), [loaded, tasks, projects, agents, approvals, content, health, tick, refresh, onOpenTask, onOpenProject, onOpenCommandMenu]);

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}
