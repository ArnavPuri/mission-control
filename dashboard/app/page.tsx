'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import * as api from './lib/api';
import * as Checkbox from '@radix-ui/react-checkbox';
import * as Progress from '@radix-ui/react-progress';
import * as Popover from '@radix-ui/react-popover';
import * as Dialog from '@radix-ui/react-dialog';
import * as ScrollArea from '@radix-ui/react-scroll-area';
import * as Tooltip from '@radix-ui/react-tooltip';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import * as Tabs from '@radix-ui/react-tabs';
import {
  Search, Bell, Plus, Play, Square, Check, X, ChevronRight,
  Zap, FolderOpen, ListTodo, Lightbulb, BookOpen, Target,
  Flame, PenLine, Clock, DollarSign, Activity, Shield,
  ExternalLink, CircleDot, Loader2, Sun, Moon, Filter,
  Pencil, Calendar, TrendingUp, BarChart3, FileText, Pin,
  GripVertical, Sparkles, BellRing, GitBranch,
} from 'lucide-react';
import { clsx } from 'clsx';

// ─── Theme ───────────────────────────────────────────────

type Theme = 'light' | 'dark';

function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setThemeState] = useState<Theme>('light');

  useEffect(() => {
    const stored = localStorage.getItem('mc-theme') as Theme | null;
    if (stored) {
      setThemeState(stored);
      document.documentElement.classList.toggle('dark', stored === 'dark');
    }
  }, []);

  const setTheme = (t: Theme) => {
    setThemeState(t);
    localStorage.setItem('mc-theme', t);
    document.documentElement.classList.toggle('dark', t === 'dark');
  };

  return [theme, setTheme];
}

// ─── Shared UI Primitives ────────────────────────────────

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={clsx('bg-white dark:bg-gray-900 rounded-xl border border-mc-border dark:border-gray-800 shadow-card', className)}>
      {children}
    </div>
  );
}

function Badge({ children, variant = 'default' }: {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'error' | 'purple' | 'blue';
}) {
  const styles: Record<string, string> = {
    default: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
    success: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400',
    warning: 'bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-400',
    error: 'bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-400',
    purple: 'bg-violet-50 text-violet-700 dark:bg-violet-950 dark:text-violet-400',
    blue: 'bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-400',
  };
  return (
    <span className={clsx('inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium', styles[variant])}>
      {children}
    </span>
  );
}

function SectionHeader({ icon: Icon, title, count, onAdd, extra }: {
  icon: React.ElementType; title: string; count: number; onAdd?: () => void; extra?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-2">
        <Icon size={15} className="text-mc-muted dark:text-gray-500" />
        <h3 className="text-sm font-semibold text-mc-text dark:text-gray-100">{title}</h3>
        <span className="text-xs text-mc-dim dark:text-gray-500 font-medium">{count}</span>
      </div>
      <div className="flex items-center gap-2">
        {extra}
        {onAdd && (
          <button
            onClick={onAdd}
            className="w-7 h-7 rounded-lg border border-mc-border dark:border-gray-700 bg-white dark:bg-gray-800 text-mc-muted dark:text-gray-400 hover:bg-mc-accent-light hover:text-mc-accent dark:hover:bg-blue-950 dark:hover:text-blue-400 hover:border-mc-accent/30 transition-all flex items-center justify-center cursor-pointer"
          >
            <Plus size={14} />
          </button>
        )}
      </div>
    </div>
  );
}

function InlineInput({ placeholder, onSubmit, onCancel }: {
  placeholder: string; onSubmit: (v: string) => void; onCancel: () => void;
}) {
  const [val, setVal] = useState('');
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { ref.current?.focus(); }, []);
  return (
    <div className="flex gap-2 mb-3">
      <input
        ref={ref} value={val} onChange={(e) => setVal(e.target.value)} placeholder={placeholder}
        onKeyDown={(e) => { if (e.key === 'Enter' && val.trim()) { onSubmit(val.trim()); setVal(''); } if (e.key === 'Escape') onCancel(); }}
        className="flex-1 border border-mc-border dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-mc-text dark:text-gray-200 bg-white dark:bg-gray-800 outline-none focus:border-mc-accent focus:ring-2 focus:ring-mc-accent/10 placeholder:text-mc-dim transition-all"
      />
      <button
        onClick={() => { if (val.trim()) { onSubmit(val.trim()); setVal(''); } }}
        className="px-3 py-2 bg-mc-accent text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors cursor-pointer"
      >
        Add
      </button>
      <button onClick={onCancel} className="px-2 py-2 bg-white dark:bg-gray-800 border border-mc-border dark:border-gray-700 text-mc-muted rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors cursor-pointer">
        <X size={14} />
      </button>
    </div>
  );
}

function StatusIndicator({ status }: { status: string }) {
  const config: Record<string, { color: string; pulse: boolean }> = {
    running: { color: 'bg-emerald-500', pulse: true },
    active: { color: 'bg-emerald-500', pulse: true },
    idle: { color: 'bg-gray-300 dark:bg-gray-600', pulse: false },
    planning: { color: 'bg-amber-400', pulse: false },
    paused: { color: 'bg-amber-400', pulse: false },
    error: { color: 'bg-red-500', pulse: false },
    disabled: { color: 'bg-gray-200 dark:bg-gray-700', pulse: false },
    archived: { color: 'bg-gray-200 dark:bg-gray-700', pulse: false },
  };
  const c = config[status] || { color: 'bg-gray-300', pulse: false };
  return (
    <span className="relative flex h-2.5 w-2.5">
      {c.pulse && <span className={clsx('animate-ping absolute inline-flex h-full w-full rounded-full opacity-50', c.color)} />}
      <span className={clsx('relative inline-flex rounded-full h-2.5 w-2.5', c.color)} />
    </span>
  );
}

// ─── Panels ──────────────────────────────────────────────

function HealthBadge({ projectId }: { projectId: string }) {
  const [health, setHealth] = useState<api.ProjectHealth | null>(null);
  useEffect(() => {
    api.projects.health(projectId).then(setHealth).catch(() => {});
  }, [projectId]);
  if (!health) return null;
  const colors: Record<string, string> = {
    healthy: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400',
    needs_attention: 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400',
    at_risk: 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400',
  };
  return (
    <Tooltip.Provider>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <span className={clsx('inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold tabular-nums', colors[health.status])}>
            {health.score}
          </span>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            className="bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 text-[11px] px-3 py-2 rounded-lg shadow-lg max-w-[200px] z-50"
            sideOffset={5}
          >
            <div className="font-medium mb-1">{health.status.replace('_', ' ')}</div>
            <div>Done: {health.metrics.completion_rate}%</div>
            <div>Velocity: {health.metrics.weekly_velocity}/wk</div>
            {health.metrics.overdue_tasks > 0 && <div className="text-red-300 dark:text-red-600">Overdue: {health.metrics.overdue_tasks}</div>}
            <Tooltip.Arrow className="fill-gray-900 dark:fill-gray-100" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}

function ProjectsPanel({ projects }: { projects: api.Project[] }) {
  if (projects.length === 0) return <EmptyState icon={FolderOpen} message="No projects yet" />;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {projects.map((p, i) => (
        <div
          key={p.id}
          className="animate-fade-up bg-white dark:bg-gray-900 rounded-xl border border-mc-border dark:border-gray-800 p-4 hover:shadow-card-hover transition-all cursor-pointer"
          style={{ borderLeftWidth: 3, borderLeftColor: p.color, animationDelay: `${i * 40}ms` }}
        >
          <div className="flex items-center gap-2 mb-1.5">
            <StatusIndicator status={p.status} />
            <span className="text-sm font-semibold text-mc-text dark:text-gray-100 truncate">{p.name}</span>
            <HealthBadge projectId={p.id} />
          </div>
          <p className="text-xs text-mc-muted dark:text-gray-500 leading-relaxed truncate mb-3">{p.description}</p>
          <div className="flex items-center gap-2">
            <Badge variant={p.status === 'active' ? 'success' : 'warning'}>{p.status}</Badge>
            <span className="text-[11px] text-mc-dim dark:text-gray-600">{p.task_count} tasks · {p.agent_count} agents</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function AgentsPanel({ agents, projects, onToggle }: {
  agents: api.Agent[]; projects: api.Project[];
  onToggle: (id: string, action: 'run' | 'stop') => void;
}) {
  if (agents.length === 0) return <EmptyState icon={Zap} message="No agents configured" />;
  return (
    <div className="flex flex-col gap-2">
      {agents.map((a, i) => {
        const proj = projects.find((p) => p.id === a.project_id);
        const isRunning = a.status === 'running';
        return (
          <div
            key={a.id}
            className="animate-fade-up bg-white dark:bg-gray-900 rounded-xl border border-mc-border dark:border-gray-800 px-4 py-3 flex items-center gap-3 hover:shadow-card-hover transition-all"
            style={{ animationDelay: `${i * 30}ms` }}
          >
            <StatusIndicator status={a.status} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-mc-text dark:text-gray-100">{a.name}</span>
                <Badge>{a.agent_type}</Badge>
                {proj && <Badge variant="blue">{proj.name}</Badge>}
              </div>
              <div className="flex items-center gap-3 mt-0.5">
                <span className="text-xs text-mc-muted dark:text-gray-500 truncate hidden sm:block">{a.description}</span>
                {a.schedule_value && (
                  <span className="flex items-center gap-1 text-[11px] text-mc-dim shrink-0">
                    <Clock size={10} /> {a.schedule_value}
                  </span>
                )}
              </div>
            </div>
            <span className="text-xs text-mc-dim whitespace-nowrap hidden md:block">
              {a.last_run_at ? new Date(a.last_run_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : 'Never'}
            </span>
            <button
              onClick={() => onToggle(a.id, isRunning ? 'stop' : 'run')}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer border',
                isRunning
                  ? 'bg-red-50 dark:bg-red-950 border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 hover:bg-red-100'
                  : 'bg-emerald-50 dark:bg-emerald-950 border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-100',
              )}
            >
              {isRunning ? <><Square size={11} /> Stop</> : <><Play size={11} /> Run</>}
            </button>
          </div>
        );
      })}
    </div>
  );
}

// ─── Editable Task Row ───────────────────────────────────

function EditableTaskRow({ task, onToggle, onUpdate, onDelete }: {
  task: api.Task;
  onToggle: () => void;
  onUpdate: (data: Partial<api.Task>) => void;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(task.text);
  const inputRef = useRef<HTMLInputElement>(null);
  const done = task.status === 'done';

  const priorityDots: Record<string, string> = {
    critical: 'bg-red-500', high: 'bg-orange-400', medium: 'bg-amber-400', low: 'bg-gray-300',
  };
  const priorityOrder: api.Task['priority'][] = ['critical', 'high', 'medium', 'low'];

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const saveEdit = () => {
    if (editText.trim() && editText.trim() !== task.text) {
      onUpdate({ text: editText.trim() });
    }
    setEditing(false);
  };

  return (
    <div className={clsx('flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-mc-subtle dark:hover:bg-gray-800 transition-colors group', done && 'opacity-50')}>
      <Checkbox.Root
        checked={done}
        onCheckedChange={onToggle}
        className={clsx(
          'w-[18px] h-[18px] rounded border-2 flex items-center justify-center transition-all cursor-pointer shrink-0',
          done ? 'bg-mc-accent border-mc-accent' : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 hover:border-mc-accent',
        )}
      >
        <Checkbox.Indicator>
          <Check size={12} className="text-white" strokeWidth={3} />
        </Checkbox.Indicator>
      </Checkbox.Root>

      {editing ? (
        <input
          ref={inputRef}
          value={editText}
          onChange={(e) => setEditText(e.target.value)}
          onBlur={saveEdit}
          onKeyDown={(e) => { if (e.key === 'Enter') saveEdit(); if (e.key === 'Escape') { setEditText(task.text); setEditing(false); } }}
          className="flex-1 text-sm bg-white dark:bg-gray-800 border border-mc-accent rounded px-2 py-0.5 outline-none text-mc-text dark:text-gray-200"
        />
      ) : (
        <span
          className={clsx('flex-1 text-sm cursor-pointer', done ? 'text-mc-dim line-through' : 'text-mc-secondary dark:text-gray-300')}
          onDoubleClick={() => { if (!done) { setEditText(task.text); setEditing(true); } }}
        >
          {task.text}
        </span>
      )}

      {task.due_date && (
        <span className="hidden sm:flex items-center gap-1 text-[11px] text-mc-dim shrink-0">
          <Calendar size={10} />
          {new Date(task.due_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
        </span>
      )}

      {/* Priority cycle on click */}
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button className={clsx('w-3 h-3 rounded-full shrink-0 cursor-pointer border-0 p-0', priorityDots[task.priority])} />
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content className="bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-700 rounded-lg shadow-dropdown p-1 z-50" sideOffset={5}>
            {priorityOrder.map((p) => (
              <DropdownMenu.Item
                key={p}
                onSelect={() => onUpdate({ priority: p })}
                className="flex items-center gap-2 px-2.5 py-1.5 rounded text-xs cursor-pointer outline-none hover:bg-mc-subtle dark:hover:bg-gray-800 transition-colors text-mc-secondary dark:text-gray-300"
              >
                <span className={clsx('w-2.5 h-2.5 rounded-full', priorityDots[p])} />
                <span className="capitalize">{p}</span>
                {p === task.priority && <Check size={12} className="ml-auto text-mc-accent" />}
              </DropdownMenu.Item>
            ))}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>

      <button
        onClick={() => { if (!done) { setEditText(task.text); setEditing(true); } }}
        className="opacity-0 group-hover:opacity-100 text-mc-dim hover:text-mc-accent transition-all cursor-pointer bg-transparent border-none p-0.5"
      >
        <Pencil size={12} />
      </button>
      <button
        onClick={onDelete}
        className="opacity-0 group-hover:opacity-100 text-mc-dim hover:text-mc-red transition-all cursor-pointer bg-transparent border-none p-0.5"
      >
        <X size={13} />
      </button>
    </div>
  );
}

function KanbanColumn({ title, tasks, color, onToggle, onUpdate, onDelete }: {
  title: string; tasks: api.Task[]; color: string;
  onToggle: (id: string) => void; onUpdate: (id: string, data: Partial<api.Task>) => void; onDelete: (id: string) => void;
}) {
  return (
    <div className="flex-1 min-w-[140px]">
      <div className="flex items-center gap-2 mb-2 px-1">
        <span className={clsx('w-2 h-2 rounded-full', color)} />
        <span className="text-[11px] font-semibold text-mc-dim uppercase tracking-wide">{title}</span>
        <span className="text-[10px] text-mc-dim">{tasks.length}</span>
      </div>
      <div className="flex flex-col gap-1.5">
        {tasks.map((t) => {
          const prioColor: Record<string, string> = { critical: 'border-l-red-500', high: 'border-l-amber-500', medium: 'border-l-blue-400', low: 'border-l-gray-300' };
          return (
            <div
              key={t.id}
              className={clsx('bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-800 rounded-lg px-2.5 py-2 hover:shadow-card-hover transition-all border-l-2', prioColor[t.priority] || 'border-l-gray-300')}
            >
              <span className="text-xs text-mc-text dark:text-gray-200 line-clamp-2 leading-relaxed">{t.text}</span>
              <div className="flex items-center gap-1 mt-1.5">
                <Badge>{t.priority}</Badge>
                {t.tags?.slice(0, 1).map((tag) => <Badge key={tag} variant="blue">{tag}</Badge>)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TasksPanel({ tasks, projects, onToggle, onUpdate, onAdd, showInput, setShowInput, onDelete, onReorder }: {
  tasks: api.Task[]; projects: api.Project[];
  onToggle: (id: string) => void; onUpdate: (id: string, data: Partial<api.Task>) => void;
  onAdd: (text: string) => void;
  showInput: boolean; setShowInput: (v: boolean) => void; onDelete: (id: string) => void;
  onReorder: (taskIds: string[]) => void;
}) {
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterPriority, setFilterPriority] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'list' | 'kanban'>('list');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [dragId, setDragId] = useState<string | null>(null);

  const filtered = tasks.filter((t) => {
    if (filterStatus !== 'all' && t.status !== filterStatus) return false;
    if (filterPriority !== 'all' && t.priority !== filterPriority) return false;
    return true;
  });

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const bulkUpdateStatus = (status: string) => {
    selected.forEach((id) => onUpdate(id, { status } as Partial<api.Task>));
    setSelected(new Set());
  };

  const bulkUpdatePriority = (priority: string) => {
    selected.forEach((id) => onUpdate(id, { priority } as Partial<api.Task>));
    setSelected(new Set());
  };

  const bulkDelete = () => {
    selected.forEach((id) => onDelete(id));
    setSelected(new Set());
  };

  const filterBar = (
    <div className="flex items-center gap-1.5 mb-3 flex-wrap">
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button className={clsx(
            'flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium border cursor-pointer transition-colors',
            filterStatus !== 'all'
              ? 'bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-400'
              : 'bg-white dark:bg-gray-800 border-mc-border dark:border-gray-700 text-mc-muted dark:text-gray-400',
          )}>
            <Filter size={10} />
            {filterStatus === 'all' ? 'Status' : filterStatus}
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content className="bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-700 rounded-lg shadow-dropdown p-1 z-50" sideOffset={5}>
            {['all', 'todo', 'in_progress', 'blocked', 'done'].map((s) => (
              <DropdownMenu.Item
                key={s}
                onSelect={() => setFilterStatus(s)}
                className="flex items-center gap-2 px-2.5 py-1.5 rounded text-xs cursor-pointer outline-none hover:bg-mc-subtle dark:hover:bg-gray-800 transition-colors text-mc-secondary dark:text-gray-300 capitalize"
              >
                {s === 'all' ? 'All statuses' : s.replace('_', ' ')}
                {s === filterStatus && <Check size={12} className="ml-auto text-mc-accent" />}
              </DropdownMenu.Item>
            ))}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>

      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button className={clsx(
            'flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium border cursor-pointer transition-colors',
            filterPriority !== 'all'
              ? 'bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-400'
              : 'bg-white dark:bg-gray-800 border-mc-border dark:border-gray-700 text-mc-muted dark:text-gray-400',
          )}>
            <Filter size={10} />
            {filterPriority === 'all' ? 'Priority' : filterPriority}
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content className="bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-700 rounded-lg shadow-dropdown p-1 z-50" sideOffset={5}>
            {['all', 'critical', 'high', 'medium', 'low'].map((p) => (
              <DropdownMenu.Item
                key={p}
                onSelect={() => setFilterPriority(p)}
                className="flex items-center gap-2 px-2.5 py-1.5 rounded text-xs cursor-pointer outline-none hover:bg-mc-subtle dark:hover:bg-gray-800 transition-colors text-mc-secondary dark:text-gray-300 capitalize"
              >
                {p === 'all' ? 'All priorities' : p}
                {p === filterPriority && <Check size={12} className="ml-auto text-mc-accent" />}
              </DropdownMenu.Item>
            ))}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>

      {(filterStatus !== 'all' || filterPriority !== 'all') && (
        <button
          onClick={() => { setFilterStatus('all'); setFilterPriority('all'); }}
          className="text-[11px] text-mc-accent cursor-pointer bg-transparent border-none hover:underline"
        >
          Clear
        </button>
      )}

      <div className="ml-auto flex items-center gap-0.5 bg-gray-100 dark:bg-gray-800 rounded-md p-0.5">
        <button
          onClick={() => setViewMode('list')}
          className={clsx('px-2 py-1 rounded text-[11px] font-medium cursor-pointer border-none transition-colors', viewMode === 'list' ? 'bg-white dark:bg-gray-700 text-mc-text dark:text-gray-200 shadow-sm' : 'bg-transparent text-mc-dim')}
        >
          List
        </button>
        <button
          onClick={() => setViewMode('kanban')}
          className={clsx('px-2 py-1 rounded text-[11px] font-medium cursor-pointer border-none transition-colors', viewMode === 'kanban' ? 'bg-white dark:bg-gray-700 text-mc-text dark:text-gray-200 shadow-sm' : 'bg-transparent text-mc-dim')}
        >
          Board
        </button>
      </div>
    </div>
  );

  // Bulk action bar
  const bulkBar = selected.size > 0 && (
    <div className="flex items-center gap-2 mb-2 px-2 py-1.5 bg-mc-accent-light dark:bg-blue-950 rounded-lg border border-mc-accent/20">
      <span className="text-xs font-medium text-mc-accent">{selected.size} selected</span>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button className="text-[11px] text-mc-accent hover:underline cursor-pointer bg-transparent border-none">Set status</button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content className="bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-700 rounded-lg shadow-dropdown p-1 z-50" sideOffset={5}>
            {['todo', 'in_progress', 'blocked', 'done'].map((s) => (
              <DropdownMenu.Item key={s} onSelect={() => bulkUpdateStatus(s)} className="px-2.5 py-1.5 rounded text-xs cursor-pointer outline-none hover:bg-mc-subtle dark:hover:bg-gray-800 capitalize text-mc-secondary dark:text-gray-300">
                {s.replace('_', ' ')}
              </DropdownMenu.Item>
            ))}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button className="text-[11px] text-mc-accent hover:underline cursor-pointer bg-transparent border-none">Set priority</button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content className="bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-700 rounded-lg shadow-dropdown p-1 z-50" sideOffset={5}>
            {['critical', 'high', 'medium', 'low'].map((p) => (
              <DropdownMenu.Item key={p} onSelect={() => bulkUpdatePriority(p)} className="px-2.5 py-1.5 rounded text-xs cursor-pointer outline-none hover:bg-mc-subtle dark:hover:bg-gray-800 capitalize text-mc-secondary dark:text-gray-300">
                {p}
              </DropdownMenu.Item>
            ))}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      <button onClick={bulkDelete} className="text-[11px] text-red-500 hover:underline cursor-pointer bg-transparent border-none">Delete</button>
      <button onClick={() => setSelected(new Set())} className="text-[11px] text-mc-dim hover:underline cursor-pointer bg-transparent border-none ml-auto">Clear</button>
    </div>
  );

  return (
    <div>
      {showInput && <InlineInput placeholder="What needs to be done?" onSubmit={onAdd} onCancel={() => setShowInput(false)} />}
      {tasks.length > 3 && filterBar}
      {bulkBar}

      {viewMode === 'list' ? (
        <div className="flex flex-col gap-0.5">
          {filtered.map((t) => (
            <div
              key={t.id}
              draggable
              onDragStart={() => setDragId(t.id)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => {
                if (dragId && dragId !== t.id) {
                  const ids = filtered.map((x) => x.id);
                  const fromIdx = ids.indexOf(dragId);
                  const toIdx = ids.indexOf(t.id);
                  if (fromIdx >= 0 && toIdx >= 0) {
                    ids.splice(fromIdx, 1);
                    ids.splice(toIdx, 0, dragId);
                    onReorder(ids);
                  }
                }
                setDragId(null);
              }}
              onDragEnd={() => setDragId(null)}
              className={clsx('flex items-center gap-0.5', dragId === t.id && 'opacity-40')}
            >
              <GripVertical size={12} className="text-mc-dim cursor-grab shrink-0 hover:text-mc-muted" />
              <input
                type="checkbox"
                checked={selected.has(t.id)}
                onChange={() => toggleSelect(t.id)}
                className="w-3.5 h-3.5 rounded border-mc-border accent-mc-accent cursor-pointer shrink-0"
              />
              <div className="flex-1 min-w-0">
                <EditableTaskRow
                  task={t}
                  onToggle={() => onToggle(t.id)}
                  onUpdate={(data) => onUpdate(t.id, data)}
                  onDelete={() => onDelete(t.id)}
                />
              </div>
            </div>
          ))}
          {filtered.length === 0 && tasks.length > 0 && (
            <div className="text-xs text-mc-dim text-center py-4">No tasks match filters</div>
          )}
          {tasks.length === 0 && !showInput && <EmptyState icon={ListTodo} message="All clear!" small />}
        </div>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {([
            { key: 'todo', title: 'To Do', color: 'bg-gray-400' },
            { key: 'in_progress', title: 'In Progress', color: 'bg-blue-500' },
            { key: 'blocked', title: 'Blocked', color: 'bg-red-500' },
            { key: 'done', title: 'Done', color: 'bg-emerald-500' },
          ] as const).map((col) => (
            <KanbanColumn
              key={col.key}
              title={col.title}
              color={col.color}
              tasks={filtered.filter((t) => t.status === col.key)}
              onToggle={onToggle}
              onUpdate={onUpdate}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function IdeasPanel({ ideas, onAdd, showInput, setShowInput, onDelete }: {
  ideas: api.Idea[]; onAdd: (text: string) => void;
  showInput: boolean; setShowInput: (v: boolean) => void; onDelete: (id: string) => void;
}) {
  return (
    <div>
      {showInput && <InlineInput placeholder="Capture an idea..." onSubmit={onAdd} onCancel={() => setShowInput(false)} />}
      <div className="flex flex-col gap-2">
        {ideas.map((idea) => (
          <div key={idea.id} className="bg-violet-50/50 dark:bg-violet-950/30 border border-violet-100 dark:border-violet-900 rounded-lg px-3.5 py-2.5 hover:bg-violet-50 dark:hover:bg-violet-950/50 transition-colors group">
            <div className="flex justify-between items-start">
              <span className="text-sm text-mc-secondary dark:text-gray-300 flex-1">{idea.text}</span>
              <button onClick={() => onDelete(idea.id)} className="opacity-0 group-hover:opacity-100 text-mc-dim hover:text-mc-red transition-all cursor-pointer bg-transparent border-none p-0.5 ml-2">
                <X size={13} />
              </button>
            </div>
            <div className="flex gap-1.5 mt-2 items-center">
              {idea.tags?.map((tag) => <Badge key={tag} variant="purple">{tag}</Badge>)}
              {idea.score != null && <Badge variant={idea.score >= 7 ? 'success' : 'warning'}>{idea.score}/10</Badge>}
              <span className="text-[11px] text-mc-dim ml-auto">
                {new Date(idea.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
              </span>
            </div>
          </div>
        ))}
        {ideas.length === 0 && !showInput && <EmptyState icon={Lightbulb} message="No ideas yet" small />}
      </div>
    </div>
  );
}

function ReadingPanel({ items, onToggle, onAdd, showInput, setShowInput, onDelete }: {
  items: api.ReadingItem[]; onToggle: (id: string) => void; onAdd: (text: string) => void;
  showInput: boolean; setShowInput: (v: boolean) => void; onDelete: (id: string) => void;
}) {
  return (
    <div>
      {showInput && <InlineInput placeholder="Title or URL..." onSubmit={onAdd} onCancel={() => setShowInput(false)} />}
      <div className="flex flex-col gap-1">
        {items.map((r) => (
          <div key={r.id} className={clsx('flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-mc-subtle dark:hover:bg-gray-800 transition-colors group', r.is_read && 'opacity-50')}>
            <Checkbox.Root
              checked={r.is_read}
              onCheckedChange={() => onToggle(r.id)}
              className={clsx(
                'w-[18px] h-[18px] rounded border-2 flex items-center justify-center transition-all cursor-pointer shrink-0',
                r.is_read ? 'bg-mc-accent border-mc-accent' : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 hover:border-mc-accent',
              )}
            >
              <Checkbox.Indicator><Check size={12} className="text-white" strokeWidth={3} /></Checkbox.Indicator>
            </Checkbox.Root>
            <span className={clsx('flex-1 text-sm truncate', r.is_read ? 'text-mc-dim line-through' : 'text-mc-secondary dark:text-gray-300')}>
              {r.url ? (
                <a href={r.url} target="_blank" rel="noopener noreferrer" className="hover:text-mc-accent transition-colors inline-flex items-center gap-1">
                  {r.title} <ExternalLink size={11} className="text-mc-dim" />
                </a>
              ) : r.title}
            </span>
            <button onClick={() => onDelete(r.id)} className="opacity-0 group-hover:opacity-100 text-mc-dim hover:text-mc-red transition-all cursor-pointer bg-transparent border-none p-0.5">
              <X size={13} />
            </button>
          </div>
        ))}
        {items.length === 0 && !showInput && <EmptyState icon={BookOpen} message="Reading list empty" small />}
      </div>
    </div>
  );
}

function HabitsPanel({ habits, onToggle, onAdd, showInput, setShowInput }: {
  habits: api.Habit[]; onToggle: (id: string) => void; onAdd: (name: string) => void;
  showInput: boolean; setShowInput: (v: boolean) => void;
}) {
  return (
    <div>
      {showInput && <InlineInput placeholder="New habit..." onSubmit={onAdd} onCancel={() => setShowInput(false)} />}
      <div className="flex flex-col gap-2">
        {habits.map((h) => (
          <div key={h.id} className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-mc-subtle dark:hover:bg-gray-800 transition-colors">
            <button
              onClick={() => onToggle(h.id)}
              className={clsx(
                'w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all cursor-pointer shrink-0',
                h.completed_today
                  ? 'border-emerald-500 bg-emerald-500'
                  : 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 hover:border-emerald-400',
              )}
            >
              {h.completed_today && <Check size={13} className="text-white" strokeWidth={3} />}
            </button>
            <div className="flex-1 min-w-0">
              <span className="text-sm text-mc-secondary dark:text-gray-300 font-medium">{h.name}</span>
            </div>
            {h.current_streak > 0 && (
              <div className="flex items-center gap-1 shrink-0">
                <Flame size={13} className="text-orange-400" />
                <span className="text-sm font-semibold text-orange-500">{h.current_streak}</span>
              </div>
            )}
          </div>
        ))}
        {habits.length === 0 && !showInput && <EmptyState icon={Flame} message="No habits yet" small />}
      </div>
    </div>
  );
}

// ─── Habit Analytics ─────────────────────────────────────

function HabitAnalyticsPanel({ analytics }: { analytics: api.HabitAnalytics | null }) {
  if (!analytics || analytics.habits.length === 0) {
    return <EmptyState icon={BarChart3} message="No habit data yet" small />;
  }

  return (
    <div className="flex flex-col gap-4">
      {analytics.habits.map((h) => {
        const pct = Math.round(h.completion_rate * 100);
        return (
          <div key={h.id} className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: h.color }} />
                <span className="text-sm font-medium text-mc-text dark:text-gray-200">{h.name}</span>
              </div>
              <div className="flex items-center gap-3 text-xs">
                <span className="text-mc-muted dark:text-gray-500">{pct}% rate</span>
                <div className="flex items-center gap-1">
                  <Flame size={11} className="text-orange-400" />
                  <span className="font-semibold text-orange-500">{h.current_streak}d</span>
                </div>
                <span className="text-mc-dim dark:text-gray-600">best {h.best_streak}d</span>
              </div>
            </div>
            {/* Weekly mini bar chart */}
            <div className="flex items-end gap-1 h-8">
              {h.weekly_data.map((w, i) => {
                const maxVal = 7;
                const height = Math.max(2, (w.completions / maxVal) * 32);
                return (
                  <Tooltip.Root key={i}>
                    <Tooltip.Trigger asChild>
                      <div
                        className="flex-1 rounded-t transition-all"
                        style={{
                          height,
                          background: w.completions >= 5 ? '#059669' : w.completions >= 3 ? '#2563eb' : w.completions > 0 ? '#93c5fd' : '#e5e7eb',
                        }}
                      />
                    </Tooltip.Trigger>
                    <Tooltip.Content className="bg-mc-text text-white text-xs px-2 py-1 rounded-md" sideOffset={5}>
                      Week {i + 1}: {w.completions}/7 days
                    </Tooltip.Content>
                  </Tooltip.Root>
                );
              })}
            </div>
            <Progress.Root className="h-1.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden" value={pct}>
              <Progress.Indicator
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${pct}%`, background: h.color }}
              />
            </Progress.Root>
          </div>
        );
      })}
    </div>
  );
}

function NotesPanel({ notes, onAdd, onDelete, onTogglePin, showInput, setShowInput }: {
  notes: api.Note[]; onAdd: (title: string) => void; onDelete: (id: string) => void;
  onTogglePin: (id: string) => void; showInput: boolean; setShowInput: (v: boolean) => void;
}) {
  return (
    <div>
      {showInput && <InlineInput placeholder="Note title..." onSubmit={onAdd} onCancel={() => setShowInput(false)} />}
      <div className="flex flex-col gap-2">
        {notes.slice(0, 8).map((n) => (
          <div key={n.id} className="bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-800 rounded-lg px-3.5 py-2.5 hover:shadow-card-hover transition-all group">
            <div className="flex items-center gap-2">
              <button onClick={() => onTogglePin(n.id)} className={clsx('shrink-0 cursor-pointer bg-transparent border-none p-0', n.is_pinned ? 'text-amber-500' : 'text-gray-300 dark:text-gray-700 hover:text-amber-400')}>
                <Pin size={12} />
              </button>
              <span className="text-sm text-mc-text dark:text-gray-200 font-medium flex-1 truncate">{n.title}</span>
              <button onClick={() => onDelete(n.id)} className="opacity-0 group-hover:opacity-100 text-mc-dim hover:text-red-500 transition-all cursor-pointer bg-transparent border-none p-0">
                <X size={12} />
              </button>
            </div>
            {n.content && (
              <p className="text-xs text-mc-muted dark:text-gray-500 mt-1 line-clamp-2">{n.content.slice(0, 120)}</p>
            )}
            <div className="flex items-center gap-1.5 mt-1.5">
              {n.tags?.map((tag) => <Badge key={tag}>{tag}</Badge>)}
              <span className="text-[10px] text-mc-dim ml-auto">
                {new Date(n.updated_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
              </span>
            </div>
          </div>
        ))}
        {notes.length === 0 && !showInput && <EmptyState icon={FileText} message="No notes yet" small />}
      </div>
    </div>
  );
}

function AgentAnalyticsPanel({ analytics, agents }: { analytics: api.AgentAnalyticsOverview | null; agents: api.Agent[] }) {
  if (!analytics || analytics.agents.length === 0) {
    return <EmptyState icon={BarChart3} message="No agent analytics yet" small />;
  }

  const { totals } = analytics;

  return (
    <div className="flex flex-col gap-3">
      {/* Summary row */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-mc-subtle dark:bg-gray-800 rounded-lg px-3 py-2 text-center">
          <div className="text-lg font-bold text-mc-text dark:text-gray-100">{totals.total_runs}</div>
          <div className="text-[11px] text-mc-dim">Total Runs</div>
        </div>
        <div className="bg-mc-subtle dark:bg-gray-800 rounded-lg px-3 py-2 text-center">
          <div className={clsx('text-lg font-bold', totals.overall_success_rate >= 80 ? 'text-emerald-600' : totals.overall_success_rate >= 50 ? 'text-amber-600' : 'text-red-600')}>
            {Math.round(totals.overall_success_rate)}%
          </div>
          <div className="text-[11px] text-mc-dim">Success</div>
        </div>
        <div className="bg-mc-subtle dark:bg-gray-800 rounded-lg px-3 py-2 text-center">
          <div className="text-lg font-bold text-mc-text dark:text-gray-100 font-mono">${totals.total_cost_usd.toFixed(2)}</div>
          <div className="text-[11px] text-mc-dim">Total Cost</div>
        </div>
      </div>

      {/* Per-agent breakdown */}
      {analytics.agents.map((a) => (
        <div key={a.agent_id} className="bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-800 rounded-lg px-3 py-2.5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-medium text-mc-text dark:text-gray-200 truncate">{a.agent_name}</span>
            <span className="text-[11px] text-mc-dim font-mono">{a.model}</span>
          </div>
          <div className="flex items-center gap-3 text-[11px]">
            <span className="text-mc-muted">{a.total_runs} runs</span>
            <span className={clsx(a.success_rate >= 80 ? 'text-emerald-600' : a.success_rate >= 50 ? 'text-amber-600' : 'text-red-500')}>
              {Math.round(a.success_rate)}% ok
            </span>
            <span className={clsx('font-mono', a.total_cost_usd > 0.5 ? 'text-amber-600' : 'text-emerald-600')}>
              ${a.total_cost_usd.toFixed(3)}
            </span>
            {a.avg_duration_seconds > 0 && (
              <span className="text-mc-dim">{Math.round(a.avg_duration_seconds)}s avg</span>
            )}
          </div>
          {/* Mini cost sparkline */}
          {Object.keys(a.daily_costs).length > 0 && (
            <div className="flex items-end gap-px mt-2 h-4">
              {Object.entries(a.daily_costs).slice(-14).map(([day, cost]) => {
                const maxCost = Math.max(...Object.values(a.daily_costs), 0.01);
                const h = Math.max(2, (cost / maxCost) * 16);
                return (
                  <div
                    key={day}
                    className="flex-1 rounded-t bg-mc-accent/40 dark:bg-blue-500/30"
                    style={{ height: `${h}px` }}
                  />
                );
              })}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function GoalsPanel({ goals, onAdd, showInput, setShowInput }: {
  goals: api.Goal[]; onAdd: (title: string) => void;
  showInput: boolean; setShowInput: (v: boolean) => void;
}) {
  return (
    <div>
      {showInput && <InlineInput placeholder="Set a goal..." onSubmit={onAdd} onCancel={() => setShowInput(false)} />}
      <div className="flex flex-col gap-3">
        {goals.map((g) => {
          const pct = Math.round(g.progress * 100);
          return (
            <div key={g.id} className="bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-800 rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-mc-text dark:text-gray-100 flex-1">{g.title}</span>
                <span className="text-sm font-semibold text-mc-accent ml-2">{pct}%</span>
              </div>
              <Progress.Root className="h-2 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden" value={pct}>
                <Progress.Indicator
                  className="h-full rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${pct}%`, background: pct >= 75 ? '#059669' : pct >= 40 ? '#d97706' : '#2563eb' }}
                />
              </Progress.Root>
              {g.key_results.length > 0 && (
                <div className="mt-3 flex flex-col gap-1.5">
                  {g.key_results.map((kr) => (
                    <div key={kr.id} className="flex items-center gap-2 text-xs">
                      <ChevronRight size={11} className="text-mc-dim shrink-0" />
                      <span className="text-mc-muted dark:text-gray-500 flex-1 truncate">{kr.title}</span>
                      <span className="text-mc-dim font-mono">{kr.current_value}/{kr.target_value} {kr.unit}</span>
                    </div>
                  ))}
                </div>
              )}
              {(g.tags?.length > 0 || g.target_date) && (
                <div className="flex gap-1.5 mt-2 items-center">
                  {g.tags?.map((tag) => <Badge key={tag} variant="warning">{tag}</Badge>)}
                  {g.target_date && (
                    <span className="text-[11px] text-mc-dim ml-auto">
                      Due {new Date(g.target_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
        {goals.length === 0 && !showInput && <EmptyState icon={Target} message="No goals yet" small />}
      </div>
    </div>
  );
}

function JournalPanel({ entries, onAdd, showInput, setShowInput, onDelete }: {
  entries: api.JournalEntry[]; onAdd: (content: string) => void;
  showInput: boolean; setShowInput: (v: boolean) => void; onDelete: (id: string) => void;
}) {
  const moodEmoji: Record<string, string> = { great: '😊', good: '🙂', okay: '😐', low: '😔', bad: '😢' };
  return (
    <div>
      {showInput && <InlineInput placeholder="What's on your mind..." onSubmit={onAdd} onCancel={() => setShowInput(false)} />}
      <div className="flex flex-col gap-2">
        {entries.slice(0, 5).map((e) => (
          <div key={e.id} className="bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-800 rounded-lg px-3.5 py-3 hover:shadow-card-hover transition-all group">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1.5">
                  {e.mood && <span className="text-sm">{moodEmoji[e.mood]}</span>}
                  <span className="text-xs text-mc-dim dark:text-gray-600 font-medium">
                    {new Date(e.created_at).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
                  </span>
                  {e.energy != null && <Badge variant="default">Energy {e.energy}/5</Badge>}
                </div>
                <p className="text-sm text-mc-secondary dark:text-gray-300 leading-relaxed line-clamp-2">{e.content.substring(0, 150)}{e.content.length > 150 ? '...' : ''}</p>
              </div>
              <button onClick={() => onDelete(e.id)} className="opacity-0 group-hover:opacity-100 text-mc-dim hover:text-mc-red transition-all cursor-pointer bg-transparent border-none p-0.5 ml-2">
                <X size={13} />
              </button>
            </div>
            {(e.wins.length > 0 || e.gratitude.length > 0) && (
              <div className="flex gap-1.5 mt-2">
                {e.wins.length > 0 && <Badge variant="success">{e.wins.length} wins</Badge>}
                {e.gratitude.length > 0 && <Badge variant="purple">{e.gratitude.length} gratitude</Badge>}
              </div>
            )}
          </div>
        ))}
        {entries.length === 0 && !showInput && <EmptyState icon={PenLine} message="No journal entries" small />}
      </div>
    </div>
  );
}

function ApprovalsPanel({ approvals, onApprove, onReject }: {
  approvals: api.Approval[]; onApprove: (id: string) => void; onReject: (id: string) => void;
}) {
  if (approvals.length === 0) return null;
  return (
    <Card className="border-amber-200 dark:border-amber-800 bg-amber-50/30 dark:bg-amber-950/20 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Shield size={15} className="text-amber-600" />
        <h3 className="text-sm font-semibold text-amber-800 dark:text-amber-400">Pending Approvals</h3>
        <Badge variant="warning">{approvals.length}</Badge>
      </div>
      <div className="flex flex-col gap-2">
        {approvals.map((a) => (
          <div key={a.id} className="bg-white dark:bg-gray-900 rounded-lg border border-amber-200 dark:border-amber-800 px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-sm font-medium text-mc-text dark:text-gray-100">{a.agent_name}</span>
                <Badge variant="warning">{a.action_count} actions</Badge>
              </div>
              <p className="text-xs text-mc-muted dark:text-gray-500 truncate">{a.summary}</p>
            </div>
            <div className="flex gap-2 shrink-0">
              <button onClick={() => onApprove(a.id)} className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-50 dark:bg-emerald-950 border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-100 transition-colors cursor-pointer">
                <Check size={12} /> Approve
              </button>
              <button onClick={() => onReject(a.id)} className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 hover:bg-red-100 transition-colors cursor-pointer">
                <X size={12} /> Reject
              </button>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ─── Notification Bell ───────────────────────────────────

function NotificationBell({ notifications, unreadCount, onMarkRead, onMarkAllRead }: {
  notifications: api.Notification[]; unreadCount: number;
  onMarkRead: (id: string) => void; onMarkAllRead: () => void;
}) {
  const categoryColors: Record<string, string> = {
    success: 'bg-emerald-500', error: 'bg-red-500', warning: 'bg-amber-500', info: 'bg-blue-500', approval: 'bg-amber-500',
  };
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button className="relative w-9 h-9 rounded-lg border border-mc-border dark:border-gray-700 bg-white dark:bg-gray-800 text-mc-muted dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700 hover:text-mc-text transition-all flex items-center justify-center cursor-pointer">
          <Bell size={16} />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 w-[18px] h-[18px] bg-red-500 rounded-full flex items-center justify-center text-[10px] text-white font-bold">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="w-80 bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-700 rounded-xl shadow-dropdown overflow-hidden z-50" sideOffset={8} align="end">
          <div className="flex items-center justify-between px-4 py-3 border-b border-mc-border dark:border-gray-800">
            <span className="text-sm font-semibold text-mc-text dark:text-gray-100">Notifications</span>
            {unreadCount > 0 && (
              <button onClick={onMarkAllRead} className="text-xs text-mc-accent bg-transparent border-none cursor-pointer hover:underline font-medium">Mark all read</button>
            )}
          </div>
          <ScrollArea.Root className="max-h-72">
            <ScrollArea.Viewport className="w-full">
              {notifications.slice(0, 10).map((n) => (
                <div
                  key={n.id}
                  className={clsx('px-4 py-3 border-b border-mc-border/50 dark:border-gray-800 hover:bg-mc-subtle dark:hover:bg-gray-800 transition-colors cursor-pointer', n.is_read && 'opacity-50')}
                  onClick={() => { if (!n.is_read) onMarkRead(n.id); }}
                >
                  <div className="flex items-center gap-2">
                    <span className={clsx('w-2 h-2 rounded-full shrink-0', categoryColors[n.category] || 'bg-gray-400')} />
                    <span className="text-sm text-mc-text dark:text-gray-200 flex-1 truncate">{n.title}</span>
                    <span className="text-[11px] text-mc-dim">{new Date(n.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                  {n.body && <p className="text-xs text-mc-muted dark:text-gray-500 mt-0.5 truncate pl-4">{n.body}</p>}
                </div>
              ))}
              {notifications.length === 0 && <div className="text-sm text-mc-dim text-center py-8">No notifications</div>}
            </ScrollArea.Viewport>
          </ScrollArea.Root>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

// ─── Activity Heatmap ────────────────────────────────────

function ActivityHeatmap({ tasks, journal }: { tasks: api.Task[]; journal: api.JournalEntry[] }) {
  const today = new Date();
  const days: { date: string; count: number; level: number }[] = [];
  for (let i = 83; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().split('T')[0];
    let count = 0;
    count += tasks.filter((t) => t.created_at.startsWith(dateStr)).length;
    count += journal.filter((j) => j.created_at.startsWith(dateStr)).length;
    const level = count === 0 ? 0 : count <= 2 ? 1 : count <= 5 ? 2 : count <= 10 ? 3 : 4;
    days.push({ date: dateStr, count, level });
  }
  const colors = ['bg-gray-100 dark:bg-gray-800', 'bg-blue-100 dark:bg-blue-900', 'bg-blue-200 dark:bg-blue-700', 'bg-blue-400 dark:bg-blue-500', 'bg-blue-600 dark:bg-blue-400'];
  return (
    <div>
      <div className="flex gap-[3px] flex-wrap">
        {days.map((d) => (
          <Tooltip.Root key={d.date}>
            <Tooltip.Trigger asChild>
              <div className={clsx('w-[11px] h-[11px] rounded-[2px]', colors[d.level])} />
            </Tooltip.Trigger>
            <Tooltip.Content className="bg-mc-text text-white text-xs px-2 py-1 rounded-md z-50" sideOffset={5}>
              {d.date}: {d.count} activities
            </Tooltip.Content>
          </Tooltip.Root>
        ))}
      </div>
      <div className="flex items-center gap-1.5 mt-2">
        <span className="text-[11px] text-mc-dim">Less</span>
        {colors.map((c, i) => <div key={i} className={clsx('w-[9px] h-[9px] rounded-[2px]', c)} />)}
        <span className="text-[11px] text-mc-dim">More</span>
        <span className="text-[11px] text-mc-dim ml-auto">Last 12 weeks</span>
      </div>
    </div>
  );
}

// ─── Command Palette ─────────────────────────────────────

function CommandPalette({ open, onClose, onAction }: {
  open: boolean; onClose: () => void;
  onAction: (action: string, value: string) => void;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<api.SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) { setQuery(''); setResults([]); setTimeout(() => inputRef.current?.focus(), 50); }
  }, [open]);

  useEffect(() => {
    if (!query.trim() || query.startsWith('/')) { setResults([]); return; }
    const timeout = setTimeout(async () => {
      setSearching(true);
      try { const res = await api.search.query(query); setResults(res.results); } catch { setResults([]); }
      setSearching(false);
    }, 200);
    return () => clearTimeout(timeout);
  }, [query]);

  const commands = [
    { label: 'Add Task', key: '/task', Icon: ListTodo },
    { label: 'Add Idea', key: '/idea', Icon: Lightbulb },
    { label: 'Add Habit', key: '/habit', Icon: Flame },
    { label: 'Set Goal', key: '/goal', Icon: Target },
    { label: 'Write Journal', key: '/journal', Icon: PenLine },
    { label: 'Add Reading', key: '/reading', Icon: BookOpen },
  ];

  const filteredCommands = query.startsWith('/')
    ? commands.filter((c) => c.key.includes(query.toLowerCase()))
    : query ? [] : commands;

  const handleSelect = (cmd: typeof commands[0]) => { onAction(cmd.key.slice(1), ''); onClose(); };

  const typeIcons: Record<string, React.ElementType> = {
    task: ListTodo, idea: Lightbulb, reading: BookOpen, goal: Target, journal: PenLine, habit: Flame, project: FolderOpen,
  };

  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/20 dark:bg-black/50 backdrop-blur-sm z-50" />
        <Dialog.Content className="fixed top-[20vh] left-1/2 -translate-x-1/2 w-[calc(100%-2rem)] max-w-lg bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-700 rounded-xl shadow-dropdown overflow-hidden z-50">
          <div className="flex items-center gap-3 px-4 py-3 border-b border-mc-border dark:border-gray-800">
            <Search size={16} className="text-mc-dim" />
            <input
              ref={inputRef} value={query} onChange={(e) => setQuery(e.target.value)}
              placeholder="Search or type / for commands..."
              className="flex-1 bg-transparent text-sm text-mc-text dark:text-gray-200 outline-none placeholder:text-mc-dim"
              onKeyDown={(e) => {
                if (e.key === 'Escape') onClose();
                if (e.key === 'Enter' && filteredCommands.length > 0 && query.startsWith('/')) handleSelect(filteredCommands[0]);
              }}
            />
            {searching && <Loader2 size={14} className="text-mc-dim animate-spin" />}
            <kbd className="text-[11px] text-mc-dim border border-mc-border dark:border-gray-700 rounded px-1.5 py-0.5 font-mono">ESC</kbd>
          </div>
          <ScrollArea.Root className="max-h-80">
            <ScrollArea.Viewport className="w-full">
              {filteredCommands.length > 0 && (
                <div className="p-2">
                  <div className="text-[11px] text-mc-dim font-medium tracking-wide uppercase px-2 py-1">Commands</div>
                  {filteredCommands.map((cmd) => (
                    <button key={cmd.key} onClick={() => handleSelect(cmd)} className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-mc-subtle dark:hover:bg-gray-800 text-left cursor-pointer bg-transparent border-none transition-colors">
                      <cmd.Icon size={15} className="text-mc-muted" />
                      <span className="text-sm text-mc-secondary dark:text-gray-300">{cmd.label}</span>
                      <span className="text-xs text-mc-dim font-mono ml-auto">{cmd.key}</span>
                    </button>
                  ))}
                </div>
              )}
              {results.length > 0 && (
                <div className="p-2">
                  <div className="text-[11px] text-mc-dim font-medium tracking-wide uppercase px-2 py-1">Results</div>
                  {results.map((r) => {
                    const RIcon = typeIcons[r.type] || CircleDot;
                    return (
                      <div key={`${r.type}-${r.id}`} className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-mc-subtle dark:hover:bg-gray-800 transition-colors">
                        <RIcon size={15} className="text-mc-muted" />
                        <div className="flex-1 min-w-0">
                          <span className="text-sm text-mc-secondary dark:text-gray-300 truncate block">{r.title}</span>
                          <span className="text-[11px] text-mc-dim">{r.type}</span>
                        </div>
                        {r.status && <Badge>{r.status}</Badge>}
                      </div>
                    );
                  })}
                </div>
              )}
              {query && !query.startsWith('/') && results.length === 0 && !searching && (
                <div className="text-sm text-mc-dim text-center py-8">No results found</div>
              )}
            </ScrollArea.Viewport>
          </ScrollArea.Root>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// ─── Connection Bar ──────────────────────────────────────

function ConnectionBar({ health }: { health: api.HealthStatus | null }) {
  if (!health) return null;
  const ok = health.status === 'ok';
  return (
    <div className="hidden md:flex items-center gap-3 text-xs text-mc-muted dark:text-gray-500">
      <span className="flex items-center gap-1.5">
        <span className={clsx('w-1.5 h-1.5 rounded-full', ok ? 'bg-emerald-500' : 'bg-red-500')} />
        DB
      </span>
      <span>LLM: {health.llm_provider}</span>
      <span>TG: {health.telegram}</span>
    </div>
  );
}

function EmptyState({ icon: Icon, message, small = false }: { icon: React.ElementType; message: string; small?: boolean }) {
  return (
    <div className={clsx('flex flex-col items-center justify-center text-mc-dim', small ? 'py-6' : 'py-10')}>
      <Icon size={small ? 20 : 28} className="mb-2 text-gray-300 dark:text-gray-700" />
      <span className={clsx('text-mc-muted dark:text-gray-500', small ? 'text-xs' : 'text-sm')}>{message}</span>
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: string | number; accent?: boolean }) {
  return (
    <div className="text-center px-3 sm:px-4">
      <div className={clsx('text-base sm:text-lg font-bold tabular-nums', accent ? 'text-mc-accent' : 'text-mc-text dark:text-gray-100')}>{value}</div>
      <div className="text-[10px] sm:text-[11px] text-mc-muted dark:text-gray-500 font-medium tracking-wide uppercase">{label}</div>
    </div>
  );
}

// ─── Quick Capture ───────────────────────────────────────

const CAPTURE_PREFIXES: Record<string, { label: string; Icon: React.ElementType }> = {
  't:': { label: 'Task', Icon: ListTodo },
  'i:': { label: 'Idea', Icon: Lightbulb },
  'r:': { label: 'Reading', Icon: BookOpen },
  'n:': { label: 'Note', Icon: FileText },
  'h:': { label: 'Habit', Icon: Flame },
  'g:': { label: 'Goal', Icon: Target },
  'j:': { label: 'Journal', Icon: PenLine },
};

function QuickCapture({ open, onClose, onCapture }: {
  open: boolean;
  onClose: () => void;
  onCapture: (type: string, text: string) => Promise<void>;
}) {
  const [input, setInput] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [lastCapture, setLastCapture] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) { setInput(''); setLastCapture(null); setTimeout(() => inputRef.current?.focus(), 50); }
  }, [open]);

  // Detect type from prefix
  const detectedPrefix = Object.keys(CAPTURE_PREFIXES).find((p) => input.toLowerCase().startsWith(p));
  const detected = detectedPrefix ? CAPTURE_PREFIXES[detectedPrefix] : null;
  const cleanText = detected ? input.slice(detectedPrefix!.length).trim() : input.trim();

  const handleSubmit = async () => {
    if (!cleanText) return;
    setSubmitting(true);
    try {
      const type = detected ? detectedPrefix!.charAt(0) : 't'; // default to task
      await onCapture(type, cleanText);
      const label = detected?.label || 'Task';
      setLastCapture(`${label} added: ${cleanText.slice(0, 50)}`);
      setInput('');
      setTimeout(() => inputRef.current?.focus(), 50);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/20 dark:bg-black/50 backdrop-blur-sm z-50" />
        <Dialog.Content className="fixed top-[18vh] left-1/2 -translate-x-1/2 w-[calc(100%-2rem)] max-w-lg bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-700 rounded-xl shadow-dropdown overflow-hidden z-50">
          <div className="flex items-center gap-3 px-4 py-3 border-b border-mc-border dark:border-gray-800">
            <Zap size={16} className="text-mc-accent" />
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Quick capture — type t: i: r: n: h: g: j: or just text..."
              className="flex-1 bg-transparent text-sm text-mc-text dark:text-gray-200 outline-none placeholder:text-mc-dim"
              onKeyDown={(e) => {
                if (e.key === 'Escape') onClose();
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
              }}
            />
            {submitting && <Loader2 size={14} className="text-mc-dim animate-spin" />}
            <kbd className="text-[11px] text-mc-dim border border-mc-border dark:border-gray-700 rounded px-1.5 py-0.5 font-mono">c</kbd>
          </div>
          <div className="px-4 py-3">
            {detected ? (
              <div className="flex items-center gap-2 text-xs text-mc-muted dark:text-gray-400">
                <detected.Icon size={13} />
                <span>Creating <strong className="text-mc-text dark:text-gray-200">{detected.label}</strong></span>
                {cleanText && <span className="text-mc-dim ml-auto">Enter to save</span>}
              </div>
            ) : (
              <div className="flex flex-wrap gap-2 text-[11px] text-mc-dim">
                {Object.entries(CAPTURE_PREFIXES).map(([prefix, { label, Icon }]) => (
                  <button
                    key={prefix}
                    onClick={() => { setInput(prefix + ' '); inputRef.current?.focus(); }}
                    className="flex items-center gap-1 px-2 py-1 rounded-md bg-mc-subtle dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors cursor-pointer border-none"
                  >
                    <Icon size={11} />
                    <span>{prefix}</span>
                    <span className="text-mc-muted">{label}</span>
                  </button>
                ))}
              </div>
            )}
            {lastCapture && (
              <div className="mt-2 flex items-center gap-2 text-xs text-emerald-600 dark:text-emerald-400">
                <Check size={13} />
                <span>{lastCapture}</span>
              </div>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// ─── Journal Search ──────────────────────────────────────

function JournalSearchPanel() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<api.JournalSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [total, setTotal] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const doSearch = async () => {
    if (!query.trim()) { setResults([]); setTotal(0); return; }
    setSearching(true);
    try {
      const res = await api.journalSearch.search(query.trim());
      setResults(res.results);
      setTotal(res.total);
    } catch { setResults([]); }
    setSearching(false);
  };

  const moodEmoji: Record<string, string> = { great: '😊', good: '🙂', okay: '😐', low: '😔', bad: '😢' };

  return (
    <div>
      <div className="flex gap-2 mb-3">
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search journal entries..."
          onKeyDown={(e) => { if (e.key === 'Enter') doSearch(); }}
          className="flex-1 border border-mc-border dark:border-gray-700 rounded-lg px-3 py-1.5 text-sm text-mc-text dark:text-gray-200 bg-white dark:bg-gray-800 outline-none focus:border-mc-accent focus:ring-2 focus:ring-mc-accent/10 placeholder:text-mc-dim transition-all"
        />
        <button onClick={doSearch} className="px-3 py-1.5 bg-mc-accent text-white text-xs font-medium rounded-lg hover:bg-blue-700 transition-colors cursor-pointer">
          {searching ? <Loader2 size={12} className="animate-spin" /> : <Search size={12} />}
        </button>
      </div>
      {total > 0 && <p className="text-[11px] text-mc-dim mb-2">{total} results found</p>}
      <div className="flex flex-col gap-2 max-h-64 overflow-y-auto">
        {results.map((r) => (
          <div key={r.id} className="bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-800 rounded-lg px-3 py-2">
            <div className="flex items-center gap-2 mb-1">
              {r.mood && <span className="text-xs">{moodEmoji[r.mood] || ''}</span>}
              <span className="text-[11px] text-mc-dim">
                {new Date(r.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
              </span>
              <span className="text-[10px] text-mc-accent font-medium ml-auto">{Math.round(r.relevance * 100)}% match</span>
            </div>
            <p className="text-xs text-mc-secondary dark:text-gray-300 line-clamp-2">{r.content.slice(0, 150)}</p>
          </div>
        ))}
      </div>
      {query && results.length === 0 && !searching && (
        <p className="text-xs text-mc-dim text-center py-4">No matching entries</p>
      )}
    </div>
  );
}

// ─── Routines Panel ──────────────────────────────────────

function RoutinesPanel({ routines, onComplete, onAdd, showInput, setShowInput }: {
  routines: api.Routine[]; onComplete: (routineId: string, completedItems: string[]) => void;
  onAdd: (name: string) => void; showInput: boolean; setShowInput: (v: boolean) => void;
}) {
  const [checked, setChecked] = useState<Record<string, Set<string>>>({});

  const toggle = (routineId: string, itemId: string) => {
    setChecked((prev) => {
      const next = { ...prev };
      const set = new Set(prev[routineId] || []);
      if (set.has(itemId)) set.delete(itemId); else set.add(itemId);
      next[routineId] = set;
      return next;
    });
  };

  const typeIcons: Record<string, string> = { morning: '🌅', evening: '🌙', custom: '📋' };

  return (
    <div>
      {showInput && <InlineInput placeholder="Routine name..." onSubmit={onAdd} onCancel={() => setShowInput(false)} />}
      <div className="flex flex-col gap-3">
        {routines.map((r) => {
          const completedSet = checked[r.id] || new Set();
          const allDone = r.items.length > 0 && completedSet.size === r.items.length;
          const estMinutes = r.items.reduce((sum, it) => sum + (it.duration_minutes || 0), 0);
          return (
            <div key={r.id} className="bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-800 rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm">{typeIcons[r.routine_type] || '📋'}</span>
                  <span className="text-sm font-semibold text-mc-text dark:text-gray-100">{r.name}</span>
                  <Badge variant={r.routine_type === 'morning' ? 'warning' : r.routine_type === 'evening' ? 'purple' : 'default'}>
                    {r.routine_type}
                  </Badge>
                </div>
                <div className="flex items-center gap-2">
                  {estMinutes > 0 && (
                    <span className="text-[11px] text-mc-dim flex items-center gap-1">
                      <Clock size={10} /> {estMinutes}m
                    </span>
                  )}
                  <span className="text-[11px] text-mc-dim">{completedSet.size}/{r.items.length}</span>
                </div>
              </div>
              {r.items.length > 0 && (
                <div className="flex flex-col gap-1">
                  {r.items.map((item) => {
                    const isDone = completedSet.has(item.id);
                    return (
                      <div key={item.id} className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-mc-subtle dark:hover:bg-gray-800 transition-colors">
                        <Checkbox.Root
                          checked={isDone}
                          onCheckedChange={() => toggle(r.id, item.id)}
                          className={clsx(
                            'w-[16px] h-[16px] rounded border-2 flex items-center justify-center transition-all cursor-pointer shrink-0',
                            isDone ? 'bg-emerald-500 border-emerald-500' : 'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 hover:border-emerald-400',
                          )}
                        >
                          <Checkbox.Indicator>
                            <Check size={10} className="text-white" strokeWidth={3} />
                          </Checkbox.Indicator>
                        </Checkbox.Root>
                        <span className={clsx('text-sm flex-1', isDone ? 'text-mc-dim line-through' : 'text-mc-secondary dark:text-gray-300')}>
                          {item.text}
                        </span>
                        {item.duration_minutes && (
                          <span className="text-[10px] text-mc-dim">{item.duration_minutes}m</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
              {allDone && r.items.length > 0 && (
                <button
                  onClick={() => { onComplete(r.id, Array.from(completedSet)); setChecked((prev) => ({ ...prev, [r.id]: new Set() })); }}
                  className="mt-2 w-full py-1.5 rounded-lg text-xs font-medium bg-emerald-50 dark:bg-emerald-950 border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-100 transition-colors cursor-pointer"
                >
                  <Check size={12} className="inline mr-1" /> Complete Routine
                </button>
              )}
              {r.items.length === 0 && (
                <p className="text-xs text-mc-dim text-center py-3">No items yet — add steps via API</p>
              )}
            </div>
          );
        })}
        {routines.length === 0 && !showInput && <EmptyState icon={Clock} message="No routines yet" small />}
      </div>
    </div>
  );
}

// ─── Calendar View ───────────────────────────────────────

function CalendarView({ tasks }: { tasks: api.Task[] }) {
  const today = new Date();
  const [viewMonth, setViewMonth] = useState(today.getMonth());
  const [viewYear, setViewYear] = useState(today.getFullYear());

  const tasksWithDue = tasks.filter((t) => t.due_date);

  const firstDay = new Date(viewYear, viewMonth, 1);
  const lastDay = new Date(viewYear, viewMonth + 1, 0);
  const startPad = firstDay.getDay(); // 0=Sun
  const totalDays = lastDay.getDate();

  const cells: { day: number; tasks: api.Task[] }[] = [];
  // Padding for days before month starts
  for (let i = 0; i < startPad; i++) cells.push({ day: 0, tasks: [] });
  for (let d = 1; d <= totalDays; d++) {
    const dateStr = `${viewYear}-${String(viewMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const dayTasks = tasksWithDue.filter((t) => t.due_date!.startsWith(dateStr));
    cells.push({ day: d, tasks: dayTasks });
  }

  const prevMonth = () => {
    if (viewMonth === 0) { setViewMonth(11); setViewYear(viewYear - 1); }
    else setViewMonth(viewMonth - 1);
  };
  const nextMonth = () => {
    if (viewMonth === 11) { setViewMonth(0); setViewYear(viewYear + 1); }
    else setViewMonth(viewMonth + 1);
  };

  const monthName = new Date(viewYear, viewMonth).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  const priorityColors: Record<string, string> = { critical: 'bg-red-500', high: 'bg-orange-400', medium: 'bg-blue-400', low: 'bg-gray-300' };

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <button onClick={prevMonth} className="px-2 py-1 rounded text-xs text-mc-muted hover:bg-mc-subtle dark:hover:bg-gray-800 cursor-pointer bg-transparent border-none transition-colors">&lt;</button>
        <span className="text-sm font-semibold text-mc-text dark:text-gray-100">{monthName}</span>
        <button onClick={nextMonth} className="px-2 py-1 rounded text-xs text-mc-muted hover:bg-mc-subtle dark:hover:bg-gray-800 cursor-pointer bg-transparent border-none transition-colors">&gt;</button>
      </div>
      <div className="grid grid-cols-7 gap-px text-center">
        {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((d) => (
          <div key={d} className="text-[10px] text-mc-dim font-medium py-1">{d}</div>
        ))}
        {cells.map((cell, idx) => {
          if (cell.day === 0) return <div key={`pad-${idx}`} />;
          const dateStr = `${viewYear}-${String(viewMonth + 1).padStart(2, '0')}-${String(cell.day).padStart(2, '0')}`;
          const isToday = dateStr === todayStr;
          const hasTasks = cell.tasks.length > 0;
          return (
            <Tooltip.Root key={idx}>
              <Tooltip.Trigger asChild>
                <div className={clsx(
                  'relative rounded-lg py-1.5 text-xs transition-colors',
                  isToday ? 'bg-mc-accent text-white font-bold' : hasTasks ? 'bg-blue-50 dark:bg-blue-950 text-mc-text dark:text-gray-200 font-medium' : 'text-mc-secondary dark:text-gray-400 hover:bg-mc-subtle dark:hover:bg-gray-800',
                )}>
                  {cell.day}
                  {hasTasks && (
                    <div className="flex justify-center gap-0.5 mt-0.5">
                      {cell.tasks.slice(0, 3).map((t) => (
                        <span key={t.id} className={clsx('w-1 h-1 rounded-full', priorityColors[t.priority] || 'bg-gray-300')} />
                      ))}
                    </div>
                  )}
                </div>
              </Tooltip.Trigger>
              {hasTasks && (
                <Tooltip.Portal>
                  <Tooltip.Content className="bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 text-[11px] px-3 py-2 rounded-lg shadow-lg max-w-[220px] z-50" sideOffset={5}>
                    {cell.tasks.map((t) => (
                      <div key={t.id} className="flex items-center gap-1.5 py-0.5">
                        <span className={clsx('w-1.5 h-1.5 rounded-full shrink-0', priorityColors[t.priority])} />
                        <span className="truncate">{t.text}</span>
                      </div>
                    ))}
                    <Tooltip.Arrow className="fill-gray-900 dark:fill-gray-100" />
                  </Tooltip.Content>
                </Tooltip.Portal>
              )}
            </Tooltip.Root>
          );
        })}
      </div>
      {tasksWithDue.length === 0 && (
        <p className="text-xs text-mc-dim text-center mt-4">No tasks with due dates</p>
      )}
    </div>
  );
}

// ─── Main Dashboard ──────────────────────────────────────

export default function Dashboard() {
  const [theme, setTheme] = useTheme();
  const [projectsList, setProjects] = useState<api.Project[]>([]);
  const [agentsList, setAgents] = useState<api.Agent[]>([]);
  const [tasksList, setTasks] = useState<api.Task[]>([]);
  const [ideasList, setIdeas] = useState<api.Idea[]>([]);
  const [readingList, setReading] = useState<api.ReadingItem[]>([]);
  const [habitsList, setHabits] = useState<api.Habit[]>([]);
  const [goalsList, setGoals] = useState<api.Goal[]>([]);
  const [journalList, setJournal] = useState<api.JournalEntry[]>([]);
  const [approvalsList, setApprovals] = useState<api.Approval[]>([]);
  const [notificationsList, setNotifications] = useState<api.Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [habitAnalytics, setHabitAnalytics] = useState<api.HabitAnalytics | null>(null);
  const [notesList, setNotes] = useState<api.Note[]>([]);
  const [agentAnalytics, setAgentAnalytics] = useState<api.AgentAnalyticsOverview | null>(null);
  const [routinesList, setRoutines] = useState<api.Routine[]>([]);
  const [healthStatus, setHealth] = useState<api.HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(new Date());

  const [showTaskInput, setShowTaskInput] = useState(false);
  const [showIdeaInput, setShowIdeaInput] = useState(false);
  const [showReadingInput, setShowReadingInput] = useState(false);
  const [showHabitInput, setShowHabitInput] = useState(false);
  const [showGoalInput, setShowGoalInput] = useState(false);
  const [showJournalInput, setShowJournalInput] = useState(false);
  const [showNoteInput, setShowNoteInput] = useState(false);
  const [showRoutineInput, setShowRoutineInput] = useState(false);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [showQuickCapture, setShowQuickCapture] = useState(false);

  const router = useRouter();

  // Vim-style keyboard shortcuts: g+key for navigation, n+key for creation
  useEffect(() => {
    let pendingPrefix: string | null = null;
    let prefixTimeout: ReturnType<typeof setTimeout> | null = null;

    const handler = (e: KeyboardEvent) => {
      // Don't trigger in inputs
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      // Cmd+K for command palette
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); setShowCommandPalette((v) => !v); return; }

      // Shift+T for theme toggle
      if (e.shiftKey && e.key === 'T') { e.preventDefault(); setTheme(theme === 'light' ? 'dark' : 'light'); return; }

      // Two-key combos: g+<key> for go, n+<key> for new
      if (pendingPrefix) {
        const combo = pendingPrefix + e.key.toLowerCase();
        pendingPrefix = null;
        if (prefixTimeout) clearTimeout(prefixTimeout);

        switch (combo) {
          case 'gd': router.push('/'); return;
          case 'gp': router.push('/projects'); return;
          case 'ga': router.push('/agents'); return;
          case 'gj': router.push('/journal'); return;
          case 'gs': router.push('/settings'); return;
          case 'nt': e.preventDefault(); setShowTaskInput(true); return;
          case 'ni': e.preventDefault(); setShowIdeaInput(true); return;
          case 'no': e.preventDefault(); setShowNoteInput(true); return;
          case 'nr': e.preventDefault(); setShowReadingInput(true); return;
          case 'nh': e.preventDefault(); setShowHabitInput(true); return;
          case 'ng': e.preventDefault(); setShowGoalInput(true); return;
          case 'nj': e.preventDefault(); setShowJournalInput(true); return;
        }
        return;
      }

      if (e.key === 'g' || e.key === 'n') {
        pendingPrefix = e.key;
        prefixTimeout = setTimeout(() => { pendingPrefix = null; }, 500);
        return;
      }

      // Single-key shortcuts
      if (e.key === 'c') { e.preventDefault(); setShowQuickCapture(true); return; }
      if (e.key === '?') setShowCommandPalette(true);
    };
    window.addEventListener('keydown', handler);
    return () => { window.removeEventListener('keydown', handler); if (prefixTimeout) clearTimeout(prefixTimeout); };
  }, [theme, setTheme, router]);

  const handleCommandAction = (action: string, _value: string) => {
    const map: Record<string, (v: boolean) => void> = {
      task: setShowTaskInput, idea: setShowIdeaInput, reading: setShowReadingInput,
      habit: setShowHabitInput, goal: setShowGoalInput, journal: setShowJournalInput, note: setShowNoteInput,
    };
    map[action]?.(true);
  };

  useEffect(() => { const i = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(i); }, []);

  const loadData = useCallback(async () => {
    try {
      const [p, a, t, i, r, h, hab, g, j, ap, notifs, unread, hAnalytics, aAnalytics, n, rout] = await Promise.all([
        api.projects.list(),
        api.agents.list(),
        api.tasks.list(),
        api.ideas.list(),
        api.reading.list(),
        api.health.check(),
        api.habits.list().catch(() => []),
        api.goals.list().catch(() => []),
        api.journal.list().catch(() => []),
        api.approvals.list().catch(() => []),
        api.notifications.list().catch(() => []),
        api.notifications.unreadCount().catch(() => ({ unread: 0 })),
        api.habits.analytics().catch(() => null),
        api.agentAnalytics.overview().catch(() => null),
        api.notes.list().catch(() => []),
        api.routines.list().catch(() => []),
      ]);
      setProjects(p); setAgents(a); setTasks(t); setIdeas(i); setReading(r); setHealth(h);
      setHabits(hab); setGoals(g); setJournal(j); setApprovals(ap);
      setNotifications(notifs); setUnreadCount(unread.unread); setHabitAnalytics(hAnalytics);
      setAgentAnalytics(aAnalytics); setNotes(n); setRoutines(rout);
      setError(null);
    } catch (e: any) {
      setError(e.message || 'Failed to connect to backend');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => { const i = setInterval(loadData, 30000); return () => clearInterval(i); }, [loadData]);

  useEffect(() => {
    const ws = api.connectWebSocket((event) => {
      if (['agent.', 'task.', 'idea.', 'approval.', 'journal.', 'goal.', 'notification.', 'habit.'].some((p) => event.type.startsWith(p))) {
        loadData();
      }
    });
    return () => { ws?.close(); };
  }, [loadData]);

  // --- Handlers ---
  const toggleAgent = async (id: string, action: 'run' | 'stop') => {
    try { if (action === 'run') await api.agents.run(id); else await api.agents.stop(id); loadData(); } catch {}
  };
  const toggleTask = async (id: string) => {
    const task = tasksList.find((t) => t.id === id); if (!task) return;
    await api.tasks.update(id, { status: task.status === 'done' ? 'todo' : 'done' }); loadData();
  };
  const updateTask = async (id: string, data: Partial<api.Task>) => {
    await api.tasks.update(id, data); loadData();
  };
  const toggleReading = async (id: string) => {
    const item = readingList.find((r) => r.id === id); if (!item) return;
    await api.reading.update(id, { is_read: !item.is_read }); loadData();
  };
  const toggleHabit = async (id: string) => {
    const habit = habitsList.find((h) => h.id === id); if (!habit) return;
    try { if (habit.completed_today) await api.habits.uncomplete(id); else await api.habits.complete(id); loadData(); } catch {}
  };

  const addTask = async (text: string) => { await api.tasks.create({ text }); setShowTaskInput(false); loadData(); };
  const addIdea = async (text: string) => { await api.ideas.create({ text }); setShowIdeaInput(false); loadData(); };
  const addReading = async (text: string) => {
    const isUrl = text.startsWith('http');
    await api.reading.create({ title: text, url: isUrl ? text : undefined });
    setShowReadingInput(false); loadData();
  };
  const addHabit = async (name: string) => { await api.habits.create({ name }); setShowHabitInput(false); loadData(); };
  const addGoal = async (title: string) => { await api.goals.create({ title }); setShowGoalInput(false); loadData(); };
  const addJournal = async (content: string) => { await api.journal.create({ content }); setShowJournalInput(false); loadData(); };

  const deleteTask = async (id: string) => { await api.tasks.delete(id); loadData(); };
  const deleteIdea = async (id: string) => { await api.ideas.delete(id); loadData(); };
  const deleteReading = async (id: string) => { await api.reading.delete(id); loadData(); };
  const deleteJournal = async (id: string) => { await api.journal.delete(id); loadData(); };
  const addNote = async (title: string) => { await api.notes.create({ title }); setShowNoteInput(false); loadData(); };
  const deleteNote = async (id: string) => { await api.notes.delete(id); loadData(); };
  const reorderTasks = async (taskIds: string[]) => { await api.taskReorder.reorder(taskIds); loadData(); };

  const handleQuickCapture = async (type: string, text: string) => {
    const handlers: Record<string, (text: string) => Promise<void>> = {
      t: async (t) => { await api.tasks.create({ text: t }); },
      i: async (t) => { await api.ideas.create({ text: t }); },
      r: async (t) => { const isUrl = t.startsWith('http'); await api.reading.create({ title: t, url: isUrl ? t : undefined }); },
      n: async (t) => { await api.notes.create({ title: t }); },
      h: async (t) => { await api.habits.create({ name: t }); },
      g: async (t) => { await api.goals.create({ title: t }); },
      j: async (t) => { await api.journal.create({ content: t }); },
    };
    await (handlers[type] || handlers.t)(text);
    loadData();
  };
  const addRoutine = async (name: string) => {
    await api.routines.create({ name, routine_type: 'custom' });
    setShowRoutineInput(false); loadData();
  };
  const completeRoutine = async (routineId: string, completedItems: string[]) => {
    await api.routines.complete(routineId, completedItems); loadData();
  };

  const toggleNotePin = async (id: string) => {
    const note = notesList.find((n) => n.id === id); if (!note) return;
    await api.notes.update(id, { is_pinned: !note.is_pinned }); loadData();
  };

  const handleApprove = async (id: string) => { await api.approvals.approve(id); loadData(); };
  const handleReject = async (id: string) => { await api.approvals.reject(id); loadData(); };
  const markNotifRead = async (id: string) => { await api.notifications.markRead(id); loadData(); };
  const markAllNotifsRead = async () => { await api.notifications.markAllRead(); loadData(); };

  // --- Stats ---
  const runningAgents = agentsList.filter((a) => a.status === 'running').length;
  const activeProjects = projectsList.filter((p) => p.status === 'active').length;
  const openTasks = tasksList.filter((t) => t.status !== 'done').length;
  const activeGoals = goalsList.filter((g) => g.status === 'active').length;
  const todayHabits = habitsList.filter((h) => h.completed_today).length;

  if (loading) {
    return (
      <div className="min-h-screen bg-mc-bg dark:bg-gray-950 flex items-center justify-center">
        <div className="text-center">
          <Loader2 size={24} className="text-mc-accent animate-spin mx-auto mb-4" />
          <p className="text-sm text-mc-muted dark:text-gray-500">Connecting to Mission Control...</p>
        </div>
      </div>
    );
  }

  return (
    <Tooltip.Provider delayDuration={200}>
      <div className="min-h-screen bg-mc-bg dark:bg-gray-950 transition-colors">
        {/* Top Bar */}
        <header className="px-4 sm:px-6 lg:px-8 py-3 bg-white dark:bg-gray-900 border-b border-mc-border dark:border-gray-800 sticky top-0 z-30">
          <div className="max-w-[1600px] mx-auto flex items-center justify-between">
            <div className="flex items-center gap-2 sm:gap-4">
              <h1 className="text-sm sm:text-base font-bold text-mc-text dark:text-gray-100 tracking-tight">Dashboard</h1>
              <span className="text-[11px] text-mc-dim font-medium bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded hidden sm:block">v0.3</span>
              <ConnectionBar health={healthStatus} />
            </div>

            <div className="flex items-center gap-2 sm:gap-3">
              <button
                onClick={() => setShowCommandPalette(true)}
                className="flex items-center gap-2 px-2 sm:px-3 py-1.5 bg-mc-subtle dark:bg-gray-800 border border-mc-border dark:border-gray-700 rounded-lg text-mc-muted hover:bg-gray-100 dark:hover:bg-gray-700 hover:border-gray-300 transition-all cursor-pointer"
              >
                <Search size={14} />
                <span className="text-sm hidden md:block">Search...</span>
                <kbd className="text-[10px] text-mc-dim border border-mc-border dark:border-gray-700 rounded px-1.5 py-0.5 font-mono bg-white dark:bg-gray-900 hidden md:block">⌘K</kbd>
              </button>
              <NotificationBell
                notifications={notificationsList} unreadCount={unreadCount}
                onMarkRead={markNotifRead} onMarkAllRead={markAllNotifsRead}
              />
              {error && <span className="text-xs text-mc-red font-medium hidden sm:block">{error}</span>}
            </div>
          </div>
        </header>

        {/* Stats Bar */}
        <div className="bg-white dark:bg-gray-900 border-b border-mc-border dark:border-gray-800">
          <div className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between overflow-x-auto">
            <div className="flex items-center divide-x divide-mc-border dark:divide-gray-800">
              <StatCard label="Projects" value={activeProjects} accent />
              <StatCard label="Agents" value={`${runningAgents}/${agentsList.length}`} accent={runningAgents > 0} />
              <StatCard label="Tasks" value={openTasks} />
              <StatCard label="Habits" value={`${todayHabits}/${habitsList.length}`} accent={todayHabits === habitsList.length && habitsList.length > 0} />
              <StatCard label="Goals" value={activeGoals} />
            </div>
            <div className="text-sm text-mc-muted dark:text-gray-500 font-mono tabular-nums hidden md:block">
              {now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
              <span className="ml-3 text-mc-dim">{now.toLocaleTimeString('en-US', { hour12: false })}</span>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <main className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-6">
          <div className="flex flex-col gap-4 sm:gap-6">
            {approvalsList.length > 0 && (
              <ApprovalsPanel approvals={approvalsList} onApprove={handleApprove} onReject={handleReject} />
            )}

            <section>
              <SectionHeader icon={FolderOpen} title="Projects" count={projectsList.length} />
              <ProjectsPanel projects={projectsList} />
            </section>

            <section>
              <SectionHeader icon={Zap} title="Agents" count={agentsList.length} />
              <AgentsPanel agents={agentsList} projects={projectsList} onToggle={toggleAgent} />
            </section>

            {/* 3-Column Layout — stacks on mobile */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
              <Card className="p-4">
                <SectionHeader icon={ListTodo} title="Tasks" count={openTasks} onAdd={() => setShowTaskInput(true)} />
                <TasksPanel
                  tasks={tasksList} projects={projectsList} onToggle={toggleTask} onUpdate={updateTask}
                  onAdd={addTask} showInput={showTaskInput} setShowInput={setShowTaskInput} onDelete={deleteTask}
                  onReorder={reorderTasks}
                />
              </Card>

              <div className="flex flex-col gap-4 sm:gap-6">
                <Card className="p-4">
                  <SectionHeader icon={Clock} title="Routines" count={routinesList.length} onAdd={() => setShowRoutineInput(true)} />
                  <RoutinesPanel routines={routinesList} onComplete={completeRoutine} onAdd={addRoutine} showInput={showRoutineInput} setShowInput={setShowRoutineInput} />
                </Card>
                <Card className="p-4">
                  <SectionHeader icon={Flame} title="Habits" count={habitsList.length} onAdd={() => setShowHabitInput(true)} />
                  <HabitsPanel habits={habitsList} onToggle={toggleHabit} onAdd={addHabit} showInput={showHabitInput} setShowInput={setShowHabitInput} />
                </Card>
                <Card className="p-4">
                  <SectionHeader icon={Target} title="Goals" count={activeGoals} onAdd={() => setShowGoalInput(true)} />
                  <GoalsPanel goals={goalsList} onAdd={addGoal} showInput={showGoalInput} setShowInput={setShowGoalInput} />
                </Card>
              </div>

              <div className="flex flex-col gap-4 sm:gap-6">
                <Card className="p-4">
                  <SectionHeader icon={PenLine} title="Journal" count={journalList.length} onAdd={() => setShowJournalInput(true)} />
                  <JournalPanel entries={journalList} onAdd={addJournal} showInput={showJournalInput} setShowInput={setShowJournalInput} onDelete={deleteJournal} />
                  {journalList.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-mc-border dark:border-gray-800">
                      <div className="flex items-center gap-1.5 mb-2">
                        <Search size={12} className="text-mc-dim" />
                        <span className="text-[11px] font-medium text-mc-dim">Journal Search</span>
                      </div>
                      <JournalSearchPanel />
                    </div>
                  )}
                </Card>
                <Card className="p-4">
                  <SectionHeader icon={Lightbulb} title="Ideas" count={ideasList.length} onAdd={() => setShowIdeaInput(true)} />
                  <IdeasPanel ideas={ideasList} onAdd={addIdea} showInput={showIdeaInput} setShowInput={setShowIdeaInput} onDelete={deleteIdea} />
                </Card>
                <Card className="p-4">
                  <SectionHeader icon={FileText} title="Notes" count={notesList.length} onAdd={() => setShowNoteInput(true)} />
                  <NotesPanel notes={notesList} onAdd={addNote} onDelete={deleteNote} onTogglePin={toggleNotePin} showInput={showNoteInput} setShowInput={setShowNoteInput} />
                </Card>
                <Card className="p-4">
                  <SectionHeader icon={BookOpen} title="Reading List" count={readingList.filter((r) => !r.is_read).length} onAdd={() => setShowReadingInput(true)} />
                  <ReadingPanel items={readingList} onToggle={toggleReading} onAdd={addReading} showInput={showReadingInput} setShowInput={setShowReadingInput} onDelete={deleteReading} />
                </Card>
              </div>
            </div>

            {/* Bottom Row: Calendar + Analytics + Activity + Costs */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
              <Card className="p-4">
                <SectionHeader icon={Calendar} title="Calendar" count={tasksList.filter((t) => t.due_date).length} />
                <CalendarView tasks={tasksList} />
              </Card>

              <Card className="p-4">
                <SectionHeader icon={TrendingUp} title="Habit Analytics" count={habitsList.length} />
                <HabitAnalyticsPanel analytics={habitAnalytics} />
              </Card>

              <Card className="p-4">
                <SectionHeader icon={Activity} title="Activity" count={tasksList.length + journalList.length} />
                <ActivityHeatmap tasks={tasksList} journal={journalList} />
              </Card>

              <Card className="p-4">
                <SectionHeader icon={BarChart3} title="Agent Analytics" count={agentsList.length} />
                <AgentAnalyticsPanel analytics={agentAnalytics} agents={agentsList} />
              </Card>
            </div>
          </div>
        </main>

        <CommandPalette open={showCommandPalette} onClose={() => setShowCommandPalette(false)} onAction={handleCommandAction} />
        <QuickCapture open={showQuickCapture} onClose={() => setShowQuickCapture(false)} onCapture={handleQuickCapture} />
      </div>
    </Tooltip.Provider>
  );
}
