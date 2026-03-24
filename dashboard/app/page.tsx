'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import * as api from './lib/api';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import * as Dialog from '@radix-ui/react-dialog';
import {
  Search, Bell, Plus, Play, Check, X, ChevronRight,
  FolderOpen, ListTodo, Clock, Activity,
  Loader2, Sun, Moon, Pencil, FileText, Pin,
  Bot, StickyNote, Megaphone,
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

// ─── Helper ──────────────────────────────────────────────

function timeAgo(dateStr: string | undefined): string {
  if (!dateStr) return 'never';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

const PRIORITY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
const PRIORITY_VARIANT: Record<string, 'error' | 'warning' | 'blue' | 'default'> = {
  critical: 'error', high: 'warning', medium: 'blue', low: 'default',
};

// ─── Tasks Section ───────────────────────────────────────

function TasksSection({ tasks, onRefresh }: { tasks: api.Task[]; onRefresh: () => void }) {
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');

  const openTasks = tasks
    .filter((t) => t.status !== 'done')
    .sort((a, b) => (PRIORITY_ORDER[a.priority] ?? 9) - (PRIORITY_ORDER[b.priority] ?? 9));

  const handleAdd = async (text: string) => {
    await api.tasks.create({ text, status: 'todo', priority: 'medium' });
    setAdding(false);
    onRefresh();
  };

  const handleComplete = async (id: string) => {
    await api.tasks.update(id, { status: 'done' });
    onRefresh();
  };

  const handleEditSave = async (id: string) => {
    if (editText.trim()) {
      await api.tasks.update(id, { text: editText.trim() });
      onRefresh();
    }
    setEditingId(null);
  };

  const handlePriorityChange = async (id: string, priority: string) => {
    await api.tasks.update(id, { priority: priority as api.Task['priority'] });
    onRefresh();
  };

  return (
    <Card className="p-4">
      <SectionHeader icon={ListTodo} title="Tasks" count={openTasks.length} onAdd={() => setAdding(true)} />
      {adding && <InlineInput placeholder="New task..." onSubmit={handleAdd} onCancel={() => setAdding(false)} />}
      <div className="space-y-1 max-h-[400px] overflow-y-auto">
        {openTasks.length === 0 && (
          <p className="text-sm text-mc-dim dark:text-gray-500 py-4 text-center">No open tasks</p>
        )}
        {openTasks.map((task) => (
          <div
            key={task.id}
            className="group flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/60 transition-colors"
          >
            <button
              onClick={() => handleComplete(task.id)}
              className="flex-shrink-0 w-5 h-5 rounded-full border-2 border-mc-border dark:border-gray-600 hover:border-mc-accent hover:bg-mc-accent-light dark:hover:border-blue-500 dark:hover:bg-blue-950 transition-all flex items-center justify-center cursor-pointer"
            >
              <Check size={10} className="text-transparent group-hover:text-mc-accent dark:group-hover:text-blue-400" />
            </button>
            {editingId === task.id ? (
              <input
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                onBlur={() => handleEditSave(task.id)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleEditSave(task.id); if (e.key === 'Escape') setEditingId(null); }}
                autoFocus
                className="flex-1 text-sm bg-transparent border-b border-mc-accent outline-none text-mc-text dark:text-gray-200"
              />
            ) : (
              <span
                className="flex-1 text-sm text-mc-text dark:text-gray-300 truncate cursor-pointer"
                onDoubleClick={() => { setEditingId(task.id); setEditText(task.text); }}
              >
                {task.text}
              </span>
            )}
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <button className="flex-shrink-0 cursor-pointer">
                  <Badge variant={PRIORITY_VARIANT[task.priority]}>{task.priority}</Badge>
                </button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content className="bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-700 rounded-lg shadow-dropdown p-1 z-50" sideOffset={4}>
                  {['critical', 'high', 'medium', 'low'].map((p) => (
                    <DropdownMenu.Item
                      key={p}
                      onSelect={() => handlePriorityChange(task.id, p)}
                      className="px-3 py-1.5 text-sm text-mc-text dark:text-gray-300 rounded cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 outline-none capitalize"
                    >
                      {p}
                    </DropdownMenu.Item>
                  ))}
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
            {task.due_date && (
              <span className="text-[11px] text-mc-dim dark:text-gray-500 flex-shrink-0">
                <Clock size={10} className="inline mr-0.5" />
                {new Date(task.due_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
              </span>
            )}
            <button
              onClick={() => { setEditingId(task.id); setEditText(task.text); }}
              className="opacity-0 group-hover:opacity-100 text-mc-dim hover:text-mc-text dark:hover:text-gray-200 transition-all cursor-pointer"
            >
              <Pencil size={12} />
            </button>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ─── Projects Section ────────────────────────────────────

function ProjectsSection({ projects }: { projects: api.Project[] }) {
  const statusVariant: Record<string, 'success' | 'warning' | 'default' | 'purple'> = {
    active: 'success', planning: 'warning', launched: 'purple', paused: 'default', archived: 'default',
  };

  return (
    <Card className="p-4">
      <SectionHeader icon={FolderOpen} title="Projects" count={projects.length} />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {projects.length === 0 && (
          <p className="text-sm text-mc-dim dark:text-gray-500 py-4 text-center col-span-2">No projects</p>
        )}
        {projects.map((project) => (
          <div
            key={project.id}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-mc-border dark:border-gray-800 hover:shadow-card-hover transition-shadow"
          >
            <div
              className="w-2.5 h-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: project.color || '#6b7280' }}
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-mc-text dark:text-gray-200 truncate">
                  {project.name}
                </span>
                <Badge variant={statusVariant[project.status] || 'default'}>{project.status}</Badge>
              </div>
              <div className="flex items-center gap-3 mt-0.5 text-[11px] text-mc-dim dark:text-gray-500">
                <span>{project.open_task_count} open tasks</span>
                {project.agent_count > 0 && <span>{project.agent_count} agents</span>}
              </div>
            </div>
            <ChevronRight size={14} className="text-mc-dim dark:text-gray-600 flex-shrink-0" />
          </div>
        ))}
      </div>
    </Card>
  );
}

// ─── Agents Section ──────────────────────────────────────

function AgentsSection({ agents, onRefresh }: { agents: api.Agent[]; onRefresh: () => void }) {
  const [runningId, setRunningId] = useState<string | null>(null);

  const handleRun = async (id: string) => {
    setRunningId(id);
    try {
      await api.agents.triggerRun(id);
      onRefresh();
    } catch {
      // error handled silently
    } finally {
      setRunningId(null);
    }
  };

  const statusVariant: Record<string, 'success' | 'error' | 'default'> = {
    running: 'success', error: 'error', idle: 'default', disabled: 'default',
  };

  return (
    <Card className="p-4">
      <SectionHeader icon={Bot} title="Agents" count={agents.length} />
      <div className="space-y-2 max-h-[350px] overflow-y-auto">
        {agents.length === 0 && (
          <p className="text-sm text-mc-dim dark:text-gray-500 py-4 text-center">No agents configured</p>
        )}
        {agents.map((agent) => (
          <div
            key={agent.id}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-mc-border dark:border-gray-800 hover:shadow-card-hover transition-shadow"
          >
            <StatusIndicator status={agent.status} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-mc-text dark:text-gray-200 truncate">
                  {agent.name}
                </span>
                <Badge variant={statusVariant[agent.status] || 'default'}>{agent.status}</Badge>
              </div>
              <div className="flex items-center gap-3 mt-0.5 text-[11px] text-mc-dim dark:text-gray-500">
                <span>{agent.model}</span>
                <span>Last run: {timeAgo(agent.last_run_at)}</span>
                {agent.schedule_value && <span>Every {agent.schedule_value}</span>}
              </div>
            </div>
            <button
              onClick={() => handleRun(agent.id)}
              disabled={agent.status === 'disabled' || agent.status === 'running' || runningId === agent.id}
              className={clsx(
                'w-8 h-8 rounded-lg flex items-center justify-center transition-all cursor-pointer',
                agent.status === 'disabled' || agent.status === 'running'
                  ? 'bg-gray-100 dark:bg-gray-800 text-mc-dim cursor-not-allowed'
                  : 'bg-mc-accent-light dark:bg-blue-950 text-mc-accent dark:text-blue-400 hover:bg-mc-accent hover:text-white dark:hover:bg-blue-900'
              )}
            >
              {runningId === agent.id ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            </button>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ─── Notes Section ───────────────────────────────────────

function NotesSection({ notes, onRefresh }: { notes: api.Note[]; onRefresh: () => void }) {
  const [adding, setAdding] = useState(false);

  const sorted = [...notes].sort((a, b) => {
    if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1;
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
  });

  const handleAdd = async (title: string) => {
    await api.notes.create({ title, content: '', source: 'dashboard' });
    setAdding(false);
    onRefresh();
  };

  return (
    <Card className="p-4">
      <SectionHeader icon={StickyNote} title="Notes" count={notes.length} onAdd={() => setAdding(true)} />
      {adding && <InlineInput placeholder="Note title..." onSubmit={handleAdd} onCancel={() => setAdding(false)} />}
      <div className="space-y-1 max-h-[300px] overflow-y-auto">
        {sorted.length === 0 && (
          <p className="text-sm text-mc-dim dark:text-gray-500 py-4 text-center">No notes yet</p>
        )}
        {sorted.slice(0, 10).map((note) => (
          <div
            key={note.id}
            className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/60 transition-colors"
          >
            {note.is_pinned ? (
              <Pin size={12} className="text-mc-accent dark:text-blue-400 flex-shrink-0" />
            ) : (
              <FileText size={12} className="text-mc-dim dark:text-gray-500 flex-shrink-0" />
            )}
            <span className="flex-1 text-sm text-mc-text dark:text-gray-300 truncate">
              {note.title || 'Untitled'}
            </span>
            {note.tags.length > 0 && (
              <Badge variant="default">{note.tags[0]}{note.tags.length > 1 ? ` +${note.tags.length - 1}` : ''}</Badge>
            )}
            <span className="text-[11px] text-mc-dim dark:text-gray-500 flex-shrink-0">
              {timeAgo(note.updated_at)}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ─── Content Section ─────────────────────────────────────

function ContentSection({ content }: { content: api.MarketingContent[] }) {
  const statusVariant: Record<string, 'default' | 'warning' | 'success' | 'purple'> = {
    draft: 'warning', approved: 'blue' as any, posted: 'success', archived: 'default',
  };

  const recent = [...content]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 8);

  return (
    <Card className="p-4">
      <SectionHeader icon={Megaphone} title="Content" count={content.length} />
      <div className="space-y-1 max-h-[300px] overflow-y-auto">
        {recent.length === 0 && (
          <p className="text-sm text-mc-dim dark:text-gray-500 py-4 text-center">No content drafts</p>
        )}
        {recent.map((item) => (
          <div
            key={item.id}
            className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/60 transition-colors"
          >
            <span className="flex-1 text-sm text-mc-text dark:text-gray-300 truncate">
              {item.title}
            </span>
            <Badge variant="purple">{item.channel}</Badge>
            <Badge variant={statusVariant[item.status] || 'default'}>{item.status}</Badge>
            <span className="text-[11px] text-mc-dim dark:text-gray-500 flex-shrink-0">
              {timeAgo(item.created_at)}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ─── Notification Panel ──────────────────────────────────

function NotificationPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [items, setItems] = useState<api.Notification[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      setLoading(true);
      api.notifications.list(false, 20).then(setItems).finally(() => setLoading(false));
    }
  }, [open]);

  const handleMarkAllRead = async () => {
    await api.notifications.markAllRead();
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
  };

  const categoryIcon: Record<string, 'success' | 'warning' | 'error' | 'blue' | 'purple' | 'default'> = {
    success: 'success', warning: 'warning', error: 'error', approval: 'purple', info: 'blue',
  };

  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/30 z-40" />
        <Dialog.Content className="fixed right-4 top-16 w-96 max-h-[500px] bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-800 rounded-xl shadow-dropdown z-50 flex flex-col overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-mc-border dark:border-gray-800">
            <Dialog.Title className="text-sm font-semibold text-mc-text dark:text-gray-100">Notifications</Dialog.Title>
            <div className="flex items-center gap-2">
              <button onClick={handleMarkAllRead} className="text-[11px] text-mc-accent hover:underline cursor-pointer">
                Mark all read
              </button>
              <Dialog.Close className="text-mc-dim hover:text-mc-text dark:hover:text-gray-200 cursor-pointer">
                <X size={16} />
              </Dialog.Close>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 size={20} className="animate-spin text-mc-dim" />
              </div>
            )}
            {!loading && items.length === 0 && (
              <p className="text-sm text-mc-dim dark:text-gray-500 py-8 text-center">No notifications</p>
            )}
            {!loading && items.map((n) => (
              <div
                key={n.id}
                className={clsx(
                  'px-4 py-3 border-b border-mc-border/50 dark:border-gray-800/50 hover:bg-gray-50 dark:hover:bg-gray-800/40',
                  !n.is_read && 'bg-blue-50/50 dark:bg-blue-950/20'
                )}
              >
                <div className="flex items-start gap-2">
                  <Badge variant={categoryIcon[n.category] || 'default'}>{n.category}</Badge>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-mc-text dark:text-gray-200 truncate">{n.title}</p>
                    <p className="text-xs text-mc-muted dark:text-gray-400 mt-0.5 line-clamp-2">{n.body}</p>
                    <span className="text-[10px] text-mc-dim dark:text-gray-500 mt-1 block">{timeAgo(n.created_at)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// ─── Search Dialog ───────────────────────────────────────

function SearchDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
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
    if (!query.trim()) { setResults([]); return; }
    const timeout = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await api.search.query(query.trim());
        setResults(res.results);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(timeout);
  }, [query]);

  const typeIcon: Record<string, string> = {
    task: 'T', project: 'P', note: 'N', agent: 'A',
  };

  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/30 z-40" />
        <Dialog.Content className="fixed left-1/2 top-[20%] -translate-x-1/2 w-full max-w-lg bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-800 rounded-xl shadow-dropdown z-50 overflow-hidden">
          <Dialog.Title className="sr-only">Search</Dialog.Title>
          <div className="flex items-center gap-3 px-4 py-3 border-b border-mc-border dark:border-gray-800">
            <Search size={16} className="text-mc-dim" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search tasks, projects, notes..."
              className="flex-1 bg-transparent text-sm text-mc-text dark:text-gray-200 outline-none placeholder:text-mc-dim"
            />
            {searching && <Loader2 size={14} className="animate-spin text-mc-dim" />}
          </div>
          {results.length > 0 && (
            <div className="max-h-72 overflow-y-auto py-1">
              {results.map((r) => (
                <div key={`${r.type}-${r.id}`} className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 dark:hover:bg-gray-800/60 cursor-pointer">
                  <span className="w-5 h-5 rounded bg-gray-100 dark:bg-gray-800 text-[10px] font-bold text-mc-muted flex items-center justify-center">
                    {typeIcon[r.type] || '?'}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-mc-text dark:text-gray-200 truncate">{r.title}</p>
                    <p className="text-[11px] text-mc-dim dark:text-gray-500">{r.type}{r.status ? ` / ${r.status}` : ''}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
          {query.trim() && !searching && results.length === 0 && (
            <p className="text-sm text-mc-dim dark:text-gray-500 py-6 text-center">No results found</p>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// ─── Main Dashboard ──────────────────────────────────────

export default function Dashboard() {
  const [theme, setTheme] = useTheme();
  const [tasks, setTasks] = useState<api.Task[]>([]);
  const [projects, setProjects] = useState<api.Project[]>([]);
  const [agents, setAgents] = useState<api.Agent[]>([]);
  const [notesList, setNotesList] = useState<api.Note[]>([]);
  const [content, setContent] = useState<api.MarketingContent[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showSearch, setShowSearch] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [t, p, a, n, c, nc] = await Promise.all([
        api.tasks.list(),
        api.projects.list(),
        api.agents.list(),
        api.notes.list(),
        api.marketingContent.list(),
        api.notifications.count(),
      ]);
      setTasks(t);
      setProjects(p);
      setAgents(a);
      setNotesList(n);
      setContent(c);
      setUnreadCount(nc.unread);
    } catch {
      // silent — API may not be up
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // WebSocket for live updates
  useEffect(() => {
    const ws = api.connectWebSocket((event) => {
      if (['task_created', 'task_updated', 'task_deleted', 'agent_run_completed', 'notification'].includes(event.type)) {
        fetchAll();
      }
    });
    return () => { ws?.close(); };
  }, [fetchAll]);

  // Keyboard shortcut: Cmd+K for search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setShowSearch(true);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-mc-bg dark:bg-gray-950 flex items-center justify-center">
        <Loader2 size={32} className="animate-spin text-mc-accent" />
      </div>
    );
  }

  const openTaskCount = tasks.filter((t) => t.status !== 'done').length;
  const activeAgents = agents.filter((a) => a.status === 'running').length;

  return (
    <div className="min-h-screen bg-mc-bg dark:bg-gray-950">
      {/* ─── Header ─── */}
      <header className="sticky top-0 z-30 bg-white/80 dark:bg-gray-900/80 backdrop-blur-md border-b border-mc-border dark:border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity size={20} className="text-mc-accent" />
            <h1 className="text-base font-bold text-mc-text dark:text-gray-100">Mission Control</h1>
          </div>

          <div className="flex items-center gap-2">
            {/* Search */}
            <button
              onClick={() => setShowSearch(true)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-mc-border dark:border-gray-700 bg-white dark:bg-gray-800 text-mc-muted dark:text-gray-400 hover:border-mc-accent/40 transition-all text-sm cursor-pointer"
            >
              <Search size={14} />
              <span className="hidden sm:inline">Search</span>
              <kbd className="hidden sm:inline text-[10px] bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded font-mono">
                {typeof navigator !== 'undefined' && /Mac/.test(navigator.userAgent) ? '\u2318' : 'Ctrl+'}K
              </kbd>
            </button>

            {/* Notifications */}
            <button
              onClick={() => setShowNotifications(true)}
              className="relative w-9 h-9 rounded-lg border border-mc-border dark:border-gray-700 bg-white dark:bg-gray-800 text-mc-muted dark:text-gray-400 hover:border-mc-accent/40 transition-all flex items-center justify-center cursor-pointer"
            >
              <Bell size={16} />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 bg-mc-red text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </button>

            {/* Theme toggle */}
            <button
              onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
              className="w-9 h-9 rounded-lg border border-mc-border dark:border-gray-700 bg-white dark:bg-gray-800 text-mc-muted dark:text-gray-400 hover:border-mc-accent/40 transition-all flex items-center justify-center cursor-pointer"
            >
              {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
            </button>
          </div>
        </div>
      </header>

      {/* ─── Stats bar ─── */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
        <div className="flex flex-wrap gap-4 text-sm">
          <div className="flex items-center gap-2 text-mc-muted dark:text-gray-400">
            <ListTodo size={14} />
            <span><strong className="text-mc-text dark:text-gray-200">{openTaskCount}</strong> open tasks</span>
          </div>
          <div className="flex items-center gap-2 text-mc-muted dark:text-gray-400">
            <FolderOpen size={14} />
            <span><strong className="text-mc-text dark:text-gray-200">{projects.filter(p => p.status === 'active').length}</strong> active projects</span>
          </div>
          <div className="flex items-center gap-2 text-mc-muted dark:text-gray-400">
            <Bot size={14} />
            <span><strong className="text-mc-text dark:text-gray-200">{activeAgents}</strong> agents running</span>
          </div>
          <div className="flex items-center gap-2 text-mc-muted dark:text-gray-400">
            <Megaphone size={14} />
            <span><strong className="text-mc-text dark:text-gray-200">{content.filter(c => c.status === 'draft').length}</strong> content drafts</span>
          </div>
        </div>
      </div>

      {/* ─── Main Grid ─── */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 pb-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <TasksSection tasks={tasks} onRefresh={fetchAll} />
          <AgentsSection agents={agents} onRefresh={fetchAll} />
          <ProjectsSection projects={projects} />
          <NotesSection notes={notesList} onRefresh={fetchAll} />
          <div className="lg:col-span-2">
            <ContentSection content={content} />
          </div>
        </div>
      </main>

      {/* ─── Dialogs ─── */}
      <NotificationPanel open={showNotifications} onClose={() => { setShowNotifications(false); api.notifications.count().then(nc => setUnreadCount(nc.unread)).catch(() => {}); }} />
      <SearchDialog open={showSearch} onClose={() => setShowSearch(false)} />
    </div>
  );
}
