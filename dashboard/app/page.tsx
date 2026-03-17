'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import * as api from './lib/api';
import * as Checkbox from '@radix-ui/react-checkbox';
import * as Progress from '@radix-ui/react-progress';
import * as Popover from '@radix-ui/react-popover';
import * as Dialog from '@radix-ui/react-dialog';
import * as ScrollArea from '@radix-ui/react-scroll-area';
import * as Tooltip from '@radix-ui/react-tooltip';
import * as Tabs from '@radix-ui/react-tabs';
import * as Separator from '@radix-ui/react-separator';
import {
  Search, Bell, Plus, Play, Square, Check, X, ChevronRight,
  Zap, FolderOpen, ListTodo, Lightbulb, BookOpen, Target,
  Flame, PenLine, Clock, DollarSign, Activity, Shield,
  ExternalLink, MoreHorizontal, CircleDot, Loader2,
} from 'lucide-react';
import { clsx } from 'clsx';

// ─── Shared UI Primitives ────────────────────────────────

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={clsx('bg-white rounded-xl border border-mc-border shadow-card', className)}>
      {children}
    </div>
  );
}

function Badge({ children, variant = 'default' }: {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'error' | 'purple' | 'blue';
}) {
  const styles: Record<string, string> = {
    default: 'bg-gray-100 text-gray-600',
    success: 'bg-emerald-50 text-emerald-700',
    warning: 'bg-amber-50 text-amber-700',
    error: 'bg-red-50 text-red-700',
    purple: 'bg-violet-50 text-violet-700',
    blue: 'bg-blue-50 text-blue-700',
  };
  return (
    <span className={clsx('inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium', styles[variant])}>
      {children}
    </span>
  );
}

function SectionHeader({ icon: Icon, title, count, onAdd }: {
  icon: React.ElementType; title: string; count: number; onAdd?: () => void;
}) {
  return (
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-2">
        <Icon size={15} className="text-mc-muted" />
        <h3 className="text-sm font-semibold text-mc-text">{title}</h3>
        <span className="text-xs text-mc-dim font-medium">{count}</span>
      </div>
      {onAdd && (
        <Tooltip.Provider delayDuration={200}>
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <button
                onClick={onAdd}
                className="w-7 h-7 rounded-lg border border-mc-border bg-white text-mc-muted hover:bg-mc-accent-light hover:text-mc-accent hover:border-mc-accent/30 transition-all flex items-center justify-center cursor-pointer"
              >
                <Plus size={14} />
              </button>
            </Tooltip.Trigger>
            <Tooltip.Content className="bg-mc-text text-white text-xs px-2 py-1 rounded-md" sideOffset={5}>
              Add {title.toLowerCase()}
            </Tooltip.Content>
          </Tooltip.Root>
        </Tooltip.Provider>
      )}
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
        className="flex-1 border border-mc-border rounded-lg px-3 py-2 text-sm text-mc-text bg-white outline-none focus:border-mc-accent focus:ring-2 focus:ring-mc-accent/10 placeholder:text-mc-dim transition-all"
      />
      <button
        onClick={() => { if (val.trim()) { onSubmit(val.trim()); setVal(''); } }}
        className="px-3 py-2 bg-mc-accent text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors cursor-pointer"
      >
        Add
      </button>
      <button
        onClick={onCancel}
        className="px-2 py-2 bg-white border border-mc-border text-mc-muted rounded-lg hover:bg-gray-50 transition-colors cursor-pointer"
      >
        <X size={14} />
      </button>
    </div>
  );
}

function StatusIndicator({ status }: { status: string }) {
  const config: Record<string, { color: string; pulse: boolean }> = {
    running: { color: 'bg-emerald-500', pulse: true },
    active: { color: 'bg-emerald-500', pulse: true },
    idle: { color: 'bg-gray-300', pulse: false },
    planning: { color: 'bg-amber-400', pulse: false },
    paused: { color: 'bg-amber-400', pulse: false },
    error: { color: 'bg-red-500', pulse: false },
    disabled: { color: 'bg-gray-200', pulse: false },
    archived: { color: 'bg-gray-200', pulse: false },
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

function ProjectsPanel({ projects }: { projects: api.Project[] }) {
  if (projects.length === 0) return <EmptyState icon={FolderOpen} message="No projects yet" />;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {projects.map((p, i) => (
        <div
          key={p.id}
          className="animate-fade-up bg-white rounded-xl border border-mc-border p-4 hover:shadow-card-hover hover:border-gray-300 transition-all cursor-pointer"
          style={{ borderLeftWidth: 3, borderLeftColor: p.color, animationDelay: `${i * 40}ms` }}
        >
          <div className="flex items-center gap-2 mb-1.5">
            <StatusIndicator status={p.status} />
            <span className="text-sm font-semibold text-mc-text truncate">{p.name}</span>
          </div>
          <p className="text-xs text-mc-muted leading-relaxed truncate mb-3">{p.description}</p>
          <div className="flex items-center gap-2">
            <Badge variant={p.status === 'active' ? 'success' : 'warning'}>{p.status}</Badge>
            <span className="text-[11px] text-mc-dim">{p.task_count} tasks · {p.agent_count} agents</span>
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
  const typeVariants: Record<string, 'default' | 'purple' | 'warning' | 'success' | 'error' | 'blue'> = {
    marketing: 'error', content: 'purple', research: 'warning', ops: 'success', general: 'default',
  };
  if (agents.length === 0) return <EmptyState icon={Zap} message="No agents configured" />;
  return (
    <div className="flex flex-col gap-2">
      {agents.map((a, i) => {
        const proj = projects.find((p) => p.id === a.project_id);
        const isRunning = a.status === 'running';
        return (
          <div
            key={a.id}
            className="animate-fade-up bg-white rounded-xl border border-mc-border px-4 py-3 flex items-center gap-3 hover:shadow-card-hover transition-all"
            style={{ animationDelay: `${i * 30}ms` }}
          >
            <StatusIndicator status={a.status} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-mc-text">{a.name}</span>
                <Badge variant={typeVariants[a.agent_type] || 'default'}>{a.agent_type}</Badge>
                {proj && <Badge variant="blue">{proj.name}</Badge>}
              </div>
              <div className="flex items-center gap-3 mt-0.5">
                <span className="text-xs text-mc-muted truncate">{a.description}</span>
                {a.schedule_value && (
                  <span className="flex items-center gap-1 text-[11px] text-mc-dim shrink-0">
                    <Clock size={10} /> {a.schedule_value}
                  </span>
                )}
              </div>
            </div>
            <span className="text-xs text-mc-dim whitespace-nowrap hidden sm:block">
              {a.last_run_at ? new Date(a.last_run_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'Never run'}
            </span>
            <button
              onClick={() => onToggle(a.id, isRunning ? 'stop' : 'run')}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer border',
                isRunning
                  ? 'bg-red-50 border-red-200 text-red-600 hover:bg-red-100'
                  : 'bg-emerald-50 border-emerald-200 text-emerald-700 hover:bg-emerald-100',
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

function TasksPanel({ tasks, projects, onToggle, onAdd, showInput, setShowInput, onDelete }: {
  tasks: api.Task[]; projects: api.Project[];
  onToggle: (id: string) => void; onAdd: (text: string) => void;
  showInput: boolean; setShowInput: (v: boolean) => void; onDelete: (id: string) => void;
}) {
  const priorityVariants: Record<string, 'error' | 'warning' | 'default' | 'success'> = {
    critical: 'error', high: 'error', medium: 'warning', low: 'default',
  };
  const priorityDots: Record<string, string> = {
    critical: 'bg-red-500', high: 'bg-orange-400', medium: 'bg-amber-400', low: 'bg-gray-300',
  };
  return (
    <div>
      {showInput && <InlineInput placeholder="What needs to be done?" onSubmit={onAdd} onCancel={() => setShowInput(false)} />}
      <div className="flex flex-col gap-1">
        {tasks.map((t) => {
          const done = t.status === 'done';
          return (
            <div key={t.id} className={clsx('flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-mc-subtle transition-colors group', done && 'opacity-50')}>
              <Checkbox.Root
                checked={done}
                onCheckedChange={() => onToggle(t.id)}
                className={clsx(
                  'w-[18px] h-[18px] rounded border-2 flex items-center justify-center transition-all cursor-pointer shrink-0',
                  done ? 'bg-mc-accent border-mc-accent' : 'bg-white border-gray-300 hover:border-mc-accent',
                )}
              >
                <Checkbox.Indicator>
                  <Check size={12} className="text-white" strokeWidth={3} />
                </Checkbox.Indicator>
              </Checkbox.Root>
              <span className={clsx('flex-1 text-sm', done ? 'text-mc-dim line-through' : 'text-mc-secondary')}>{t.text}</span>
              <span className={clsx('w-2 h-2 rounded-full shrink-0', priorityDots[t.priority])} />
              <button
                onClick={() => onDelete(t.id)}
                className="opacity-0 group-hover:opacity-100 text-mc-dim hover:text-mc-red transition-all cursor-pointer bg-transparent border-none p-0.5"
              >
                <X size={13} />
              </button>
            </div>
          );
        })}
        {tasks.length === 0 && !showInput && <EmptyState icon={ListTodo} message="All clear!" small />}
      </div>
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
          <div key={idea.id} className="bg-violet-50/50 border border-violet-100 rounded-lg px-3.5 py-2.5 hover:bg-violet-50 transition-colors group">
            <div className="flex justify-between items-start">
              <span className="text-sm text-mc-secondary flex-1">{idea.text}</span>
              <button
                onClick={() => onDelete(idea.id)}
                className="opacity-0 group-hover:opacity-100 text-mc-dim hover:text-mc-red transition-all cursor-pointer bg-transparent border-none p-0.5 ml-2"
              >
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
          <div key={r.id} className={clsx('flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-mc-subtle transition-colors group', r.is_read && 'opacity-50')}>
            <Checkbox.Root
              checked={r.is_read}
              onCheckedChange={() => onToggle(r.id)}
              className={clsx(
                'w-[18px] h-[18px] rounded border-2 flex items-center justify-center transition-all cursor-pointer shrink-0',
                r.is_read ? 'bg-mc-accent border-mc-accent' : 'bg-white border-gray-300 hover:border-mc-accent',
              )}
            >
              <Checkbox.Indicator>
                <Check size={12} className="text-white" strokeWidth={3} />
              </Checkbox.Indicator>
            </Checkbox.Root>
            <span className={clsx('flex-1 text-sm truncate', r.is_read ? 'text-mc-dim line-through' : 'text-mc-secondary')}>
              {r.url ? (
                <a href={r.url} target="_blank" rel="noopener noreferrer" className="hover:text-mc-accent transition-colors inline-flex items-center gap-1">
                  {r.title} <ExternalLink size={11} className="text-mc-dim" />
                </a>
              ) : r.title}
            </span>
            <button
              onClick={() => onDelete(r.id)}
              className="opacity-0 group-hover:opacity-100 text-mc-dim hover:text-mc-red transition-all cursor-pointer bg-transparent border-none p-0.5"
            >
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
          <div key={h.id} className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-mc-subtle transition-colors">
            <button
              onClick={() => onToggle(h.id)}
              className={clsx(
                'w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all cursor-pointer shrink-0',
                h.completed_today
                  ? 'border-emerald-500 bg-emerald-500'
                  : 'border-gray-300 bg-white hover:border-emerald-400',
              )}
            >
              {h.completed_today && <Check size={13} className="text-white" strokeWidth={3} />}
            </button>
            <div className="flex-1 min-w-0">
              <span className="text-sm text-mc-secondary font-medium">{h.name}</span>
              {h.description && <p className="text-xs text-mc-dim truncate">{h.description}</p>}
            </div>
            {h.current_streak > 0 && (
              <div className="flex items-center gap-1 shrink-0">
                <Flame size={13} className="text-orange-400" />
                <span className="text-sm font-semibold text-orange-500">{h.current_streak}</span>
              </div>
            )}
            <span className="text-[11px] text-mc-dim shrink-0">best {h.best_streak}d</span>
          </div>
        ))}
        {habits.length === 0 && !showInput && <EmptyState icon={Flame} message="No habits yet" small />}
      </div>
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
            <div key={g.id} className="bg-white border border-mc-border rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-mc-text flex-1">{g.title}</span>
                <span className="text-sm font-semibold text-mc-accent ml-2">{pct}%</span>
              </div>
              <Progress.Root className="h-2 bg-gray-100 rounded-full overflow-hidden" value={pct}>
                <Progress.Indicator
                  className="h-full rounded-full transition-all duration-500 ease-out"
                  style={{
                    width: `${pct}%`,
                    background: pct >= 75 ? '#059669' : pct >= 40 ? '#d97706' : '#2563eb',
                  }}
                />
              </Progress.Root>
              {g.key_results.length > 0 && (
                <div className="mt-3 flex flex-col gap-1.5">
                  {g.key_results.map((kr) => (
                    <div key={kr.id} className="flex items-center gap-2 text-xs">
                      <ChevronRight size={11} className="text-mc-dim shrink-0" />
                      <span className="text-mc-muted flex-1 truncate">{kr.title}</span>
                      <span className="text-mc-dim font-mono">
                        {kr.current_value}/{kr.target_value} {kr.unit}
                      </span>
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
  const moodVariants: Record<string, 'success' | 'blue' | 'warning' | 'error' | 'default'> = {
    great: 'success', good: 'blue', okay: 'warning', low: 'error', bad: 'error',
  };

  return (
    <div>
      {showInput && <InlineInput placeholder="What's on your mind..." onSubmit={onAdd} onCancel={() => setShowInput(false)} />}
      <div className="flex flex-col gap-2">
        {entries.slice(0, 5).map((e) => (
          <div key={e.id} className="bg-white border border-mc-border rounded-lg px-3.5 py-3 hover:shadow-card-hover transition-all group">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1.5">
                  {e.mood && <span className="text-sm">{moodEmoji[e.mood]}</span>}
                  <span className="text-xs text-mc-dim font-medium">
                    {new Date(e.created_at).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
                  </span>
                  {e.energy != null && <Badge variant="default">Energy {e.energy}/5</Badge>}
                </div>
                <p className="text-sm text-mc-secondary leading-relaxed line-clamp-2">{e.content.substring(0, 150)}{e.content.length > 150 ? '...' : ''}</p>
              </div>
              <button
                onClick={() => onDelete(e.id)}
                className="opacity-0 group-hover:opacity-100 text-mc-dim hover:text-mc-red transition-all cursor-pointer bg-transparent border-none p-0.5 ml-2"
              >
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
    <Card className="border-amber-200 bg-amber-50/30 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Shield size={15} className="text-amber-600" />
        <h3 className="text-sm font-semibold text-amber-800">Pending Approvals</h3>
        <Badge variant="warning">{approvals.length}</Badge>
      </div>
      <div className="flex flex-col gap-2">
        {approvals.map((a) => (
          <div key={a.id} className="bg-white rounded-lg border border-amber-200 px-4 py-3 flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-sm font-medium text-mc-text">{a.agent_name}</span>
                <Badge variant="warning">{a.action_count} actions</Badge>
              </div>
              <p className="text-xs text-mc-muted truncate">{a.summary}</p>
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                onClick={() => onApprove(a.id)}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-50 border border-emerald-200 text-emerald-700 hover:bg-emerald-100 transition-colors cursor-pointer"
              >
                <Check size={12} /> Approve
              </button>
              <button
                onClick={() => onReject(a.id)}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-50 border border-red-200 text-red-600 hover:bg-red-100 transition-colors cursor-pointer"
              >
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
        <button className="relative w-9 h-9 rounded-lg border border-mc-border bg-white text-mc-muted hover:bg-gray-50 hover:text-mc-text transition-all flex items-center justify-center cursor-pointer">
          <Bell size={16} />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 w-[18px] h-[18px] bg-red-500 rounded-full flex items-center justify-center text-[10px] text-white font-bold">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content className="w-80 bg-white border border-mc-border rounded-xl shadow-dropdown overflow-hidden z-50" sideOffset={8} align="end">
          <div className="flex items-center justify-between px-4 py-3 border-b border-mc-border">
            <span className="text-sm font-semibold text-mc-text">Notifications</span>
            {unreadCount > 0 && (
              <button onClick={onMarkAllRead} className="text-xs text-mc-accent bg-transparent border-none cursor-pointer hover:underline font-medium">
                Mark all read
              </button>
            )}
          </div>
          <ScrollArea.Root className="max-h-72">
            <ScrollArea.Viewport className="w-full">
              {notifications.slice(0, 10).map((n) => (
                <div
                  key={n.id}
                  className={clsx(
                    'px-4 py-3 border-b border-mc-border/50 hover:bg-mc-subtle transition-colors cursor-pointer',
                    n.is_read && 'opacity-50',
                  )}
                  onClick={() => { if (!n.is_read) onMarkRead(n.id); }}
                >
                  <div className="flex items-center gap-2">
                    <span className={clsx('w-2 h-2 rounded-full shrink-0', categoryColors[n.category] || 'bg-gray-400')} />
                    <span className="text-sm text-mc-text flex-1 truncate">{n.title}</span>
                    <span className="text-[11px] text-mc-dim">
                      {new Date(n.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  {n.body && <p className="text-xs text-mc-muted mt-0.5 truncate pl-4">{n.body}</p>}
                </div>
              ))}
              {notifications.length === 0 && (
                <div className="text-sm text-mc-dim text-center py-8">No notifications</div>
              )}
            </ScrollArea.Viewport>
            <ScrollArea.Scrollbar orientation="vertical" className="w-1.5 p-0.5">
              <ScrollArea.Thumb className="bg-gray-200 rounded-full" />
            </ScrollArea.Scrollbar>
          </ScrollArea.Root>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

// ─── Activity Heatmap ────────────────────────────────────

function ActivityHeatmap({ tasks, journal }: {
  tasks: api.Task[]; journal: api.JournalEntry[];
}) {
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

  const colors = ['bg-gray-100', 'bg-blue-100', 'bg-blue-200', 'bg-blue-400', 'bg-blue-600'];

  return (
    <div>
      <div className="flex gap-[3px] flex-wrap">
        {days.map((d) => (
          <Tooltip.Provider key={d.date} delayDuration={100}>
            <Tooltip.Root>
              <Tooltip.Trigger asChild>
                <div className={clsx('w-[11px] h-[11px] rounded-[2px]', colors[d.level])} />
              </Tooltip.Trigger>
              <Tooltip.Content className="bg-mc-text text-white text-xs px-2 py-1 rounded-md" sideOffset={5}>
                {d.date}: {d.count} activities
              </Tooltip.Content>
            </Tooltip.Root>
          </Tooltip.Provider>
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
    if (open) {
      setQuery('');
      setResults([]);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    if (!query.trim() || query.startsWith('/')) {
      setResults([]);
      return;
    }
    const timeout = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await api.search.query(query);
        setResults(res.results);
      } catch { setResults([]); }
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

  const handleSelect = (cmd: typeof commands[0]) => {
    onAction(cmd.key.slice(1), '');
    onClose();
  };

  const typeIcons: Record<string, React.ElementType> = {
    task: ListTodo, idea: Lightbulb, reading: BookOpen, goal: Target, journal: PenLine, habit: Flame, project: FolderOpen,
  };

  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/20 backdrop-blur-sm z-50" />
        <Dialog.Content className="fixed top-[20vh] left-1/2 -translate-x-1/2 w-full max-w-lg bg-white border border-mc-border rounded-xl shadow-dropdown overflow-hidden z-50">
          <div className="flex items-center gap-3 px-4 py-3 border-b border-mc-border">
            <Search size={16} className="text-mc-dim" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search or type / for commands..."
              className="flex-1 bg-transparent text-sm text-mc-text outline-none placeholder:text-mc-dim"
              onKeyDown={(e) => {
                if (e.key === 'Escape') onClose();
                if (e.key === 'Enter' && filteredCommands.length > 0 && query.startsWith('/')) handleSelect(filteredCommands[0]);
              }}
            />
            {searching && <Loader2 size={14} className="text-mc-dim animate-spin" />}
            <kbd className="text-[11px] text-mc-dim border border-mc-border rounded px-1.5 py-0.5 font-mono">ESC</kbd>
          </div>

          <ScrollArea.Root className="max-h-80">
            <ScrollArea.Viewport className="w-full">
              {filteredCommands.length > 0 && (
                <div className="p-2">
                  <div className="text-[11px] text-mc-dim font-medium tracking-wide uppercase px-2 py-1">Commands</div>
                  {filteredCommands.map((cmd) => (
                    <button
                      key={cmd.key}
                      onClick={() => handleSelect(cmd)}
                      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-mc-subtle text-left cursor-pointer bg-transparent border-none transition-colors"
                    >
                      <cmd.Icon size={15} className="text-mc-muted" />
                      <span className="text-sm text-mc-secondary">{cmd.label}</span>
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
                      <div key={`${r.type}-${r.id}`} className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-mc-subtle transition-colors">
                        <RIcon size={15} className="text-mc-muted" />
                        <div className="flex-1 min-w-0">
                          <span className="text-sm text-mc-secondary truncate block">{r.title}</span>
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
    <div className="flex items-center gap-3 text-xs text-mc-muted">
      <span className="flex items-center gap-1.5">
        <span className={clsx('w-1.5 h-1.5 rounded-full', ok ? 'bg-emerald-500' : 'bg-red-500')} />
        DB
      </span>
      <span>LLM: {health.llm_provider}</span>
      <span>TG: {health.telegram}</span>
    </div>
  );
}

// ─── Empty State ─────────────────────────────────────────

function EmptyState({ icon: Icon, message, small = false }: { icon: React.ElementType; message: string; small?: boolean }) {
  return (
    <div className={clsx('flex flex-col items-center justify-center text-mc-dim', small ? 'py-6' : 'py-10')}>
      <Icon size={small ? 20 : 28} className="mb-2 text-gray-300" />
      <span className={clsx('text-mc-muted', small ? 'text-xs' : 'text-sm')}>{message}</span>
    </div>
  );
}

// ─── Stat Card ───────────────────────────────────────────

function StatCard({ label, value, accent }: { label: string; value: string | number; accent?: boolean }) {
  return (
    <div className="text-center px-4">
      <div className={clsx('text-lg font-bold tabular-nums', accent ? 'text-mc-accent' : 'text-mc-text')}>{value}</div>
      <div className="text-[11px] text-mc-muted font-medium tracking-wide uppercase">{label}</div>
    </div>
  );
}

// ─── Main Dashboard ──────────────────────────────────────

export default function Dashboard() {
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
  const [showCommandPalette, setShowCommandPalette] = useState(false);

  // Cmd+K shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setShowCommandPalette((v) => !v);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const handleCommandAction = (action: string, _value: string) => {
    const map: Record<string, (v: boolean) => void> = {
      task: setShowTaskInput, idea: setShowIdeaInput, reading: setShowReadingInput,
      habit: setShowHabitInput, goal: setShowGoalInput, journal: setShowJournalInput,
    };
    map[action]?.(true);
  };

  // Clock
  useEffect(() => { const i = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(i); }, []);

  // Load all data
  const loadData = useCallback(async () => {
    try {
      const [p, a, t, i, r, h, hab, g, j, ap, notifs, unread] = await Promise.all([
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
      ]);
      setProjects(p);
      setAgents(a);
      setTasks(t);
      setIdeas(i);
      setReading(r);
      setHealth(h);
      setHabits(hab);
      setGoals(g);
      setJournal(j);
      setApprovals(ap);
      setNotifications(notifs);
      setUnreadCount(unread.unread);
      setError(null);
    } catch (e: any) {
      setError(e.message || 'Failed to connect to backend');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => { const i = setInterval(loadData, 30000); return () => clearInterval(i); }, [loadData]);

  // WebSocket for live updates
  useEffect(() => {
    const ws = api.connectWebSocket((event) => {
      if (event.type.startsWith('agent.') || event.type.startsWith('task.') ||
          event.type.startsWith('idea.') || event.type.startsWith('approval.') ||
          event.type.startsWith('journal.') || event.type.startsWith('goal.') ||
          event.type.startsWith('notification.')) {
        loadData();
      }
    });
    return () => { ws?.close(); };
  }, [loadData]);

  // --- Handlers ---
  const toggleAgent = async (id: string, action: 'run' | 'stop') => {
    try {
      if (action === 'run') await api.agents.run(id);
      else await api.agents.stop(id);
      loadData();
    } catch {}
  };

  const toggleTask = async (id: string) => {
    const task = tasksList.find((t) => t.id === id);
    if (!task) return;
    await api.tasks.update(id, { status: task.status === 'done' ? 'todo' : 'done' });
    loadData();
  };

  const toggleReading = async (id: string) => {
    const item = readingList.find((r) => r.id === id);
    if (!item) return;
    await api.reading.update(id, { is_read: !item.is_read });
    loadData();
  };

  const toggleHabit = async (id: string) => {
    const habit = habitsList.find((h) => h.id === id);
    if (!habit) return;
    try {
      if (habit.completed_today) await api.habits.uncomplete(id);
      else await api.habits.complete(id);
      loadData();
    } catch {}
  };

  const addTask = async (text: string) => { await api.tasks.create({ text }); setShowTaskInput(false); loadData(); };
  const addIdea = async (text: string) => { await api.ideas.create({ text }); setShowIdeaInput(false); loadData(); };
  const addReading = async (text: string) => {
    const isUrl = text.startsWith('http');
    await api.reading.create({ title: isUrl ? text : text, url: isUrl ? text : undefined });
    setShowReadingInput(false);
    loadData();
  };
  const addHabit = async (name: string) => { await api.habits.create({ name }); setShowHabitInput(false); loadData(); };
  const addGoal = async (title: string) => { await api.goals.create({ title }); setShowGoalInput(false); loadData(); };
  const addJournal = async (content: string) => { await api.journal.create({ content }); setShowJournalInput(false); loadData(); };

  const deleteTask = async (id: string) => { await api.tasks.delete(id); loadData(); };
  const deleteIdea = async (id: string) => { await api.ideas.delete(id); loadData(); };
  const deleteReading = async (id: string) => { await api.reading.delete(id); loadData(); };
  const deleteJournal = async (id: string) => { await api.journal.delete(id); loadData(); };

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

  // --- Loading state ---
  if (loading) {
    return (
      <div className="min-h-screen bg-mc-bg flex items-center justify-center">
        <div className="text-center">
          <Loader2 size={24} className="text-mc-accent animate-spin mx-auto mb-4" />
          <p className="text-sm text-mc-muted">Connecting to Mission Control...</p>
        </div>
      </div>
    );
  }

  return (
    <Tooltip.Provider delayDuration={200}>
      <div className="min-h-screen bg-mc-bg">
        {/* Header */}
        <header className="px-6 lg:px-8 py-3 bg-white border-b border-mc-border sticky top-0 z-40">
          <div className="max-w-[1600px] mx-auto flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2.5">
                <div className="w-2 h-2 rounded-full bg-mc-accent" />
                <h1 className="text-base font-bold text-mc-text tracking-tight">Mission Control</h1>
              </div>
              <span className="text-[11px] text-mc-dim font-medium bg-gray-100 px-1.5 py-0.5 rounded">v0.2</span>
              <ConnectionBar health={healthStatus} />
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowCommandPalette(true)}
                className="flex items-center gap-2 px-3 py-1.5 bg-mc-subtle border border-mc-border rounded-lg text-mc-muted hover:bg-gray-100 hover:border-gray-300 transition-all cursor-pointer"
              >
                <Search size={14} />
                <span className="text-sm hidden sm:block">Search...</span>
                <kbd className="text-[10px] text-mc-dim border border-mc-border rounded px-1.5 py-0.5 font-mono bg-white hidden sm:block">⌘K</kbd>
              </button>
              <NotificationBell
                notifications={notificationsList} unreadCount={unreadCount}
                onMarkRead={markNotifRead} onMarkAllRead={markAllNotifsRead}
              />
              {error && <span className="text-xs text-mc-red font-medium">{error}</span>}
            </div>
          </div>
        </header>

        {/* Stats Bar */}
        <div className="bg-white border-b border-mc-border">
          <div className="max-w-[1600px] mx-auto px-6 lg:px-8 py-3 flex items-center justify-between">
            <div className="flex items-center divide-x divide-mc-border">
              <StatCard label="Projects" value={activeProjects} accent />
              <StatCard label="Agents" value={`${runningAgents}/${agentsList.length}`} accent={runningAgents > 0} />
              <StatCard label="Tasks" value={openTasks} />
              <StatCard label="Habits" value={`${todayHabits}/${habitsList.length}`} accent={todayHabits === habitsList.length && habitsList.length > 0} />
              <StatCard label="Goals" value={activeGoals} />
            </div>
            <div className="text-sm text-mc-muted font-mono tabular-nums">
              {now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
              <span className="ml-3 text-mc-dim">
                {now.toLocaleTimeString('en-US', { hour12: false })}
              </span>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <main className="max-w-[1600px] mx-auto px-6 lg:px-8 py-6">
          <div className="flex flex-col gap-6">

            {/* Approvals */}
            {approvalsList.length > 0 && (
              <ApprovalsPanel approvals={approvalsList} onApprove={handleApprove} onReject={handleReject} />
            )}

            {/* Projects */}
            <section>
              <SectionHeader icon={FolderOpen} title="Projects" count={projectsList.length} />
              <ProjectsPanel projects={projectsList} />
            </section>

            {/* Agents */}
            <section>
              <SectionHeader icon={Zap} title="Agents" count={agentsList.length} />
              <AgentsPanel agents={agentsList} projects={projectsList} onToggle={toggleAgent} />
            </section>

            {/* 3-Column Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Column 1: Tasks */}
              <Card className="p-4">
                <SectionHeader icon={ListTodo} title="Tasks" count={openTasks} onAdd={() => setShowTaskInput(true)} />
                <TasksPanel
                  tasks={tasksList} projects={projectsList} onToggle={toggleTask}
                  onAdd={addTask} showInput={showTaskInput} setShowInput={setShowTaskInput} onDelete={deleteTask}
                />
              </Card>

              {/* Column 2: Habits + Goals */}
              <div className="flex flex-col gap-6">
                <Card className="p-4">
                  <SectionHeader icon={Flame} title="Habits" count={habitsList.length} onAdd={() => setShowHabitInput(true)} />
                  <HabitsPanel
                    habits={habitsList} onToggle={toggleHabit}
                    onAdd={addHabit} showInput={showHabitInput} setShowInput={setShowHabitInput}
                  />
                </Card>
                <Card className="p-4">
                  <SectionHeader icon={Target} title="Goals" count={activeGoals} onAdd={() => setShowGoalInput(true)} />
                  <GoalsPanel goals={goalsList} onAdd={addGoal} showInput={showGoalInput} setShowInput={setShowGoalInput} />
                </Card>
              </div>

              {/* Column 3: Journal + Ideas + Reading */}
              <div className="flex flex-col gap-6">
                <Card className="p-4">
                  <SectionHeader icon={PenLine} title="Journal" count={journalList.length} onAdd={() => setShowJournalInput(true)} />
                  <JournalPanel
                    entries={journalList} onAdd={addJournal}
                    showInput={showJournalInput} setShowInput={setShowJournalInput} onDelete={deleteJournal}
                  />
                </Card>
                <Card className="p-4">
                  <SectionHeader icon={Lightbulb} title="Ideas" count={ideasList.length} onAdd={() => setShowIdeaInput(true)} />
                  <IdeasPanel ideas={ideasList} onAdd={addIdea} showInput={showIdeaInput} setShowInput={setShowIdeaInput} onDelete={deleteIdea} />
                </Card>
                <Card className="p-4">
                  <SectionHeader icon={BookOpen} title="Reading List" count={readingList.filter((r) => !r.is_read).length} onAdd={() => setShowReadingInput(true)} />
                  <ReadingPanel
                    items={readingList} onToggle={toggleReading}
                    onAdd={addReading} showInput={showReadingInput} setShowInput={setShowReadingInput} onDelete={deleteReading}
                  />
                </Card>
              </div>
            </div>

            {/* Activity + Cost Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card className="p-4">
                <SectionHeader icon={Activity} title="Activity" count={tasksList.length + journalList.length} />
                <ActivityHeatmap tasks={tasksList} journal={journalList} />
              </Card>

              {agentsList.length > 0 && (
                <Card className="p-4">
                  <SectionHeader icon={DollarSign} title="Agent Costs" count={agentsList.length} />
                  <div className="grid grid-cols-2 gap-2">
                    {agentsList.map((a) => {
                      const totalCost = a.recent_runs.reduce((sum, r) => sum + (r.cost_usd || 0), 0);
                      return (
                        <div key={a.id} className="bg-mc-subtle rounded-lg px-3 py-2.5">
                          <div className="flex items-center justify-between">
                            <span className="text-xs text-mc-secondary truncate font-medium">{a.name}</span>
                            <span className={clsx('text-xs font-bold font-mono', totalCost > 0.1 ? 'text-amber-600' : 'text-emerald-600')}>
                              ${totalCost.toFixed(3)}
                            </span>
                          </div>
                          <div className="text-[11px] text-mc-dim mt-0.5">
                            {a.recent_runs.length} runs · {a.model}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </Card>
              )}
            </div>
          </div>
        </main>

        {/* Command Palette */}
        <CommandPalette
          open={showCommandPalette}
          onClose={() => setShowCommandPalette(false)}
          onAction={handleCommandAction}
        />
      </div>
    </Tooltip.Provider>
  );
}
