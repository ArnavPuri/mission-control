'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import * as api from './lib/api';

// ─── Tiny components ───────────────────────────────────────

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    running: '#00ffc8', idle: '#555', error: '#ff4444', disabled: '#333',
    active: '#00ffc8', planning: '#ffd166', paused: '#ff6b9d', archived: '#333',
  };
  const alive = status === 'running' || status === 'active';
  return (
    <span
      className={alive ? 'animate-pulse-glow' : ''}
      style={{
        display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
        background: colors[status] || '#555',
        boxShadow: alive ? `0 0 8px ${colors[status]}` : 'none',
      }}
    />
  );
}

function Badge({ children, color = '#333', textColor = '#aaa' }: { children: React.ReactNode; color?: string; textColor?: string }) {
  return (
    <span
      className="font-mono"
      style={{
        display: 'inline-block', padding: '2px 8px', borderRadius: 3,
        fontSize: 10, background: color, color: textColor,
        letterSpacing: '0.5px', textTransform: 'uppercase',
      }}
    >
      {children}
    </span>
  );
}

function SectionHeader({ icon, title, count, onAdd }: { icon: string; title: string; count: number; onAdd?: () => void }) {
  return (
    <div className="flex items-center justify-between mb-3 pb-2 border-b border-mc-border">
      <div className="flex items-center gap-2">
        <span className="text-sm opacity-50">{icon}</span>
        <h3 className="font-mono text-xs text-mc-muted tracking-widest uppercase m-0">{title}</h3>
        <span className="font-mono text-xs text-mc-dim">({count})</span>
      </div>
      {onAdd && (
        <button
          onClick={onAdd}
          className="w-6 h-6 border border-mc-border rounded text-mc-dim hover:border-mc-accent hover:text-mc-accent transition-colors flex items-center justify-center text-base leading-none bg-transparent cursor-pointer"
        >
          +
        </button>
      )}
    </div>
  );
}

function InlineInput({ placeholder, onSubmit, onCancel }: { placeholder: string; onSubmit: (v: string) => void; onCancel: () => void }) {
  const [val, setVal] = useState('');
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { ref.current?.focus(); }, []);
  return (
    <div className="flex gap-1.5 mb-2">
      <input
        ref={ref} value={val} onChange={(e) => setVal(e.target.value)} placeholder={placeholder}
        onKeyDown={(e) => { if (e.key === 'Enter' && val.trim()) { onSubmit(val.trim()); setVal(''); } if (e.key === 'Escape') onCancel(); }}
        className="flex-1 bg-mc-bg border border-mc-border rounded px-2.5 py-1.5 text-xs font-mono text-gray-300 outline-none focus:border-mc-accent/50"
      />
      <button onClick={() => { if (val.trim()) { onSubmit(val.trim()); setVal(''); } }} className="bg-mc-accent/10 border border-mc-accent/25 text-mc-accent px-2.5 py-1 rounded text-xs font-mono cursor-pointer">add</button>
      <button onClick={onCancel} className="bg-transparent border border-mc-border text-mc-dim px-2 py-1 rounded text-xs cursor-pointer">×</button>
    </div>
  );
}

function ProgressBar({ value, color = '#00ffc8' }: { value: number; color?: string }) {
  return (
    <div className="w-full h-1.5 bg-mc-border rounded-full overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{ width: `${Math.min(value * 100, 100)}%`, background: color }}
      />
    </div>
  );
}

// ─── Panels ────────────────────────────────────────────────

function ProjectsPanel({ projects }: { projects: api.Project[] }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
      {projects.map((p, i) => (
        <div
          key={p.id}
          className="animate-fade-up bg-mc-surface rounded-md p-3.5 hover:bg-[#111128] transition-colors cursor-pointer"
          style={{ borderLeft: `3px solid ${p.color}`, animationDelay: `${i * 50}ms` }}
        >
          <div className="flex items-center gap-2 mb-1.5">
            <StatusDot status={p.status} />
            <span className="text-sm font-semibold text-mc-text truncate">{p.name}</span>
          </div>
          <div className="text-[11px] text-mc-dim leading-relaxed truncate">{p.description}</div>
          <div className="flex items-center gap-2 mt-2">
            <Badge color={p.status === 'active' ? '#00ffc815' : '#ffd16615'} textColor={p.status === 'active' ? '#00ffc8' : '#ffd166'}>{p.status}</Badge>
            <span className="font-mono text-[10px] text-mc-dim">{p.task_count}t · {p.agent_count}a</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function AgentsPanel({ agents, projects, onToggle }: { agents: api.Agent[]; projects: api.Project[]; onToggle: (id: string, action: 'run' | 'stop') => void }) {
  const typeColors: Record<string, string> = { marketing: '#ff6b9d', content: '#a78bfa', research: '#ffd166', ops: '#00ffc8', general: '#888' };
  return (
    <div className="flex flex-col gap-1.5">
      {agents.map((a, i) => {
        const proj = projects.find((p) => p.id === a.project_id);
        return (
          <div
            key={a.id}
            className="animate-fade-up bg-mc-surface rounded px-3.5 py-2.5 flex items-center gap-3 hover:bg-[#111128] transition-colors"
            style={{ animationDelay: `${i * 40}ms` }}
          >
            <StatusDot status={a.status} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[13px] text-gray-200 font-medium">{a.name}</span>
                <Badge color={`${typeColors[a.agent_type] || '#888'}20`} textColor={typeColors[a.agent_type] || '#888'}>{a.agent_type}</Badge>
                {proj && <Badge color={`${proj.color}15`} textColor={proj.color}>{proj.name}</Badge>}
                {a.schedule_value && <span className="font-mono text-[9px] text-mc-dim">⏱ {a.schedule_value}</span>}
              </div>
              <div className="text-[11px] text-mc-dim mt-0.5 truncate">{a.description}</div>
            </div>
            <div className="font-mono text-[10px] text-mc-dim whitespace-nowrap">
              {a.last_run_at ? new Date(a.last_run_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'never'}
            </div>
            <button
              onClick={() => onToggle(a.id, a.status === 'running' ? 'stop' : 'run')}
              className="font-mono text-[10px] tracking-wider uppercase px-3 py-1 rounded border cursor-pointer transition-colors whitespace-nowrap"
              style={{
                background: a.status === 'running' ? '#ff444420' : '#00ffc815',
                borderColor: a.status === 'running' ? '#ff444440' : '#00ffc830',
                color: a.status === 'running' ? '#ff4444' : '#00ffc8',
              }}
            >
              {a.status === 'running' ? 'stop' : 'run'}
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
  const priorityColors: Record<string, string> = { critical: '#ff4444', high: '#ff6b9d', medium: '#ffd166', low: '#555' };
  return (
    <div>
      {showInput && <InlineInput placeholder="New task..." onSubmit={onAdd} onCancel={() => setShowInput(false)} />}
      <div className="flex flex-col gap-1">
        {tasks.map((t) => {
          const proj = projects.find((p) => p.id === t.project_id);
          const done = t.status === 'done';
          return (
            <div key={t.id} className="flex items-center gap-2.5 px-3 py-2 bg-mc-surface rounded transition-opacity" style={{ opacity: done ? 0.35 : 1 }}>
              <div
                onClick={() => onToggle(t.id)}
                className="w-4 h-4 rounded-sm border flex items-center justify-center text-[10px] cursor-pointer transition-colors shrink-0"
                style={{ borderColor: done ? '#00ffc8' : '#333', background: done ? '#00ffc820' : 'transparent', color: '#00ffc8' }}
              >
                {done && '✓'}
              </div>
              <span className="flex-1 text-xs" style={{ color: done ? '#555' : '#ccc', textDecoration: done ? 'line-through' : 'none' }}>{t.text}</span>
              {t.source !== 'manual' && <Badge color="#ffffff08" textColor="#555">{t.source}</Badge>}
              {proj && <Badge color={`${proj.color}15`} textColor={proj.color}>{proj.name}</Badge>}
              <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: priorityColors[t.priority], boxShadow: t.priority === 'critical' ? '0 0 6px #ff4444' : 'none' }} />
              <button onClick={() => onDelete(t.id)} className="bg-transparent border-none text-mc-dim hover:text-mc-red cursor-pointer text-sm px-0.5 transition-colors">×</button>
            </div>
          );
        })}
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
      {showInput && <InlineInput placeholder="New idea..." onSubmit={onAdd} onCancel={() => setShowInput(false)} />}
      <div className="flex flex-col gap-1.5">
        {ideas.map((idea) => (
          <div key={idea.id} className="bg-mc-surface rounded px-3.5 py-2.5 border-l-2 border-mc-purple/20 hover:border-mc-purple transition-colors">
            <div className="flex justify-between items-start">
              <span className="text-xs text-gray-300 flex-1">{idea.text}</span>
              <button onClick={() => onDelete(idea.id)} className="bg-transparent border-none text-mc-dim hover:text-mc-red cursor-pointer text-sm px-0.5 ml-2 transition-colors">×</button>
            </div>
            <div className="flex gap-1 mt-1.5 items-center">
              {idea.tags?.map((tag) => <Badge key={tag} color="#a78bfa15" textColor="#a78bfa">{tag}</Badge>)}
              {idea.score != null && <Badge color={idea.score >= 7 ? '#00ffc815' : '#ffd16615'} textColor={idea.score >= 7 ? '#00ffc8' : '#ffd166'}>{idea.score}/10</Badge>}
              <span className="font-mono text-[10px] text-mc-dim ml-auto">{new Date(idea.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span>
            </div>
          </div>
        ))}
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
          <div key={r.id} className="flex items-center gap-2.5 px-3 py-2 bg-mc-surface rounded" style={{ opacity: r.is_read ? 0.35 : 1 }}>
            <div
              onClick={() => onToggle(r.id)}
              className="w-4 h-4 rounded-sm border flex items-center justify-center text-[10px] cursor-pointer shrink-0"
              style={{ borderColor: r.is_read ? '#00ffc8' : '#333', background: r.is_read ? '#00ffc820' : 'transparent', color: '#00ffc8' }}
            >
              {r.is_read && '✓'}
            </div>
            <span className="flex-1 text-xs truncate" style={{ color: r.is_read ? '#555' : '#ccc', textDecoration: r.is_read ? 'line-through' : 'none' }}>
              {r.url ? <a href={r.url} target="_blank" rel="noopener noreferrer" className="hover:text-mc-accent transition-colors">{r.title}</a> : r.title}
            </span>
            <button onClick={() => onDelete(r.id)} className="bg-transparent border-none text-mc-dim hover:text-mc-red cursor-pointer text-sm px-0.5 transition-colors">×</button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── New Panels ───────────────────────────────────────────

function HabitsPanel({ habits, onToggle, onAdd, showInput, setShowInput }: {
  habits: api.Habit[]; onToggle: (id: string) => void; onAdd: (name: string) => void;
  showInput: boolean; setShowInput: (v: boolean) => void;
}) {
  return (
    <div>
      {showInput && <InlineInput placeholder="New habit..." onSubmit={onAdd} onCancel={() => setShowInput(false)} />}
      <div className="flex flex-col gap-1.5">
        {habits.map((h) => (
          <div key={h.id} className="bg-mc-surface rounded px-3.5 py-2.5 flex items-center gap-3">
            <div
              onClick={() => onToggle(h.id)}
              className="w-5 h-5 rounded-full border-2 flex items-center justify-center text-[10px] cursor-pointer transition-all shrink-0"
              style={{
                borderColor: h.completed_today ? h.color : '#333',
                background: h.completed_today ? `${h.color}30` : 'transparent',
                color: h.color,
              }}
            >
              {h.completed_today && '✓'}
            </div>
            <div className="flex-1 min-w-0">
              <span className="text-xs text-gray-200">{h.name}</span>
              {h.description && <div className="text-[10px] text-mc-dim truncate">{h.description}</div>}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {h.current_streak > 0 && (
                <span className="font-mono text-[11px] font-bold" style={{ color: h.color }}>
                  {h.current_streak}d
                </span>
              )}
              <div className="text-right">
                <div className="font-mono text-[9px] text-mc-dim">best {h.best_streak}d</div>
              </div>
            </div>
          </div>
        ))}
        {habits.length === 0 && (
          <div className="text-xs text-mc-dim text-center py-4">No habits yet. Add one to start tracking!</div>
        )}
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
      {showInput && <InlineInput placeholder="New goal..." onSubmit={onAdd} onCancel={() => setShowInput(false)} />}
      <div className="flex flex-col gap-2">
        {goals.map((g) => {
          const pct = Math.round(g.progress * 100);
          const progressColor = pct >= 75 ? '#00ffc8' : pct >= 40 ? '#ffd166' : '#ff6b9d';
          return (
            <div key={g.id} className="bg-mc-surface rounded-md p-3.5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-200 font-medium flex-1">{g.title}</span>
                <span className="font-mono text-xs font-bold ml-2" style={{ color: progressColor }}>{pct}%</span>
              </div>
              <ProgressBar value={g.progress} color={progressColor} />
              {g.key_results.length > 0 && (
                <div className="mt-2 flex flex-col gap-1">
                  {g.key_results.map((kr) => (
                    <div key={kr.id} className="flex items-center gap-2">
                      <span className="text-[10px] text-mc-dim flex-1 truncate">{kr.title}</span>
                      <span className="font-mono text-[10px] text-mc-dim">
                        {kr.current_value}/{kr.target_value} {kr.unit}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex gap-1 mt-2">
                {g.tags?.map((tag) => <Badge key={tag} color="#ffd16615" textColor="#ffd166">{tag}</Badge>)}
                {g.target_date && (
                  <span className="font-mono text-[9px] text-mc-dim ml-auto">
                    Due {new Date(g.target_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                  </span>
                )}
              </div>
            </div>
          );
        })}
        {goals.length === 0 && (
          <div className="text-xs text-mc-dim text-center py-4">No goals yet. Set your first objective!</div>
        )}
      </div>
    </div>
  );
}

function JournalPanel({ entries, onAdd, showInput, setShowInput, onDelete }: {
  entries: api.JournalEntry[]; onAdd: (content: string) => void;
  showInput: boolean; setShowInput: (v: boolean) => void; onDelete: (id: string) => void;
}) {
  const moodEmoji: Record<string, string> = { great: '✦', good: '●', okay: '○', low: '◌', bad: '×' };
  const moodColor: Record<string, string> = { great: '#00ffc8', good: '#a78bfa', okay: '#ffd166', low: '#ff6b9d', bad: '#ff4444' };

  return (
    <div>
      {showInput && <InlineInput placeholder="What's on your mind..." onSubmit={onAdd} onCancel={() => setShowInput(false)} />}
      <div className="flex flex-col gap-1.5">
        {entries.slice(0, 5).map((e) => (
          <div key={e.id} className="bg-mc-surface rounded px-3.5 py-2.5">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  {e.mood && (
                    <span className="text-xs" style={{ color: moodColor[e.mood] }}>{moodEmoji[e.mood]}</span>
                  )}
                  <span className="font-mono text-[10px] text-mc-dim">
                    {new Date(e.created_at).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
                  </span>
                  {e.energy != null && (
                    <span className="font-mono text-[9px] text-mc-dim">E:{e.energy}/5</span>
                  )}
                  {e.source !== 'manual' && <Badge color="#ffffff08" textColor="#555">{e.source}</Badge>}
                </div>
                <div className="text-xs text-gray-300 line-clamp-2">{e.content.substring(0, 150)}{e.content.length > 150 ? '...' : ''}</div>
              </div>
              <button onClick={() => onDelete(e.id)} className="bg-transparent border-none text-mc-dim hover:text-mc-red cursor-pointer text-sm px-0.5 ml-2 transition-colors">×</button>
            </div>
            {(e.wins.length > 0 || e.gratitude.length > 0) && (
              <div className="flex gap-1 mt-1.5">
                {e.wins.length > 0 && <Badge color="#00ffc815" textColor="#00ffc8">{e.wins.length} wins</Badge>}
                {e.gratitude.length > 0 && <Badge color="#a78bfa15" textColor="#a78bfa">{e.gratitude.length} gratitude</Badge>}
              </div>
            )}
          </div>
        ))}
        {entries.length === 0 && (
          <div className="text-xs text-mc-dim text-center py-4">No journal entries yet. Start writing!</div>
        )}
      </div>
    </div>
  );
}

function ApprovalsPanel({ approvals, onApprove, onReject }: {
  approvals: api.Approval[]; onApprove: (id: string) => void; onReject: (id: string) => void;
}) {
  if (approvals.length === 0) return null;
  return (
    <div className="lg:col-span-2 bg-[#1a1a0a] border border-[#ffd16640] rounded-lg p-4">
      <SectionHeader icon="⏳" title="Pending Approvals" count={approvals.length} />
      <div className="flex flex-col gap-2">
        {approvals.map((a) => (
          <div key={a.id} className="bg-mc-surface rounded px-3.5 py-2.5 flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs text-gray-200 font-medium">{a.agent_name}</span>
                <Badge color="#ffd16620" textColor="#ffd166">{a.action_count} actions</Badge>
              </div>
              <div className="text-[11px] text-mc-dim truncate">{a.summary}</div>
            </div>
            <div className="flex gap-1.5 shrink-0">
              <button
                onClick={() => onApprove(a.id)}
                className="font-mono text-[10px] tracking-wider uppercase px-3 py-1 rounded border cursor-pointer transition-colors"
                style={{ background: '#00ffc815', borderColor: '#00ffc830', color: '#00ffc8' }}
              >
                approve
              </button>
              <button
                onClick={() => onReject(a.id)}
                className="font-mono text-[10px] tracking-wider uppercase px-3 py-1 rounded border cursor-pointer transition-colors"
                style={{ background: '#ff444420', borderColor: '#ff444440', color: '#ff4444' }}
              >
                reject
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Command Palette ──────────────────────────────────────

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
    { label: 'Add Task', key: '/task', icon: '◻' },
    { label: 'Add Idea', key: '/idea', icon: '✦' },
    { label: 'Add Habit', key: '/habit', icon: '↻' },
    { label: 'Add Goal', key: '/goal', icon: '◎' },
    { label: 'Write Journal', key: '/journal', icon: '✎' },
    { label: 'Add Reading', key: '/reading', icon: '▤' },
  ];

  const filteredCommands = query.startsWith('/')
    ? commands.filter((c) => c.key.includes(query.toLowerCase()))
    : query ? [] : commands;

  const handleSelect = (cmd: typeof commands[0]) => {
    onAction(cmd.key.slice(1), '');
    onClose();
  };

  if (!open) return null;

  const typeIcons: Record<string, string> = {
    task: '◻', idea: '✦', reading: '▤', goal: '◎', journal: '✎', habit: '↻', project: '◆',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-lg bg-[#0d0d1a] border border-mc-border rounded-lg shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 py-3 border-b border-mc-border">
          <span className="text-mc-dim text-sm">⌘</span>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search or type / for commands..."
            className="flex-1 bg-transparent text-sm text-gray-200 outline-none font-mono placeholder:text-mc-dim"
            onKeyDown={(e) => {
              if (e.key === 'Escape') onClose();
              if (e.key === 'Enter' && filteredCommands.length > 0 && query.startsWith('/')) {
                handleSelect(filteredCommands[0]);
              }
            }}
          />
          {searching && <span className="text-[10px] text-mc-dim animate-pulse">searching...</span>}
          <kbd className="text-[10px] text-mc-dim border border-mc-border rounded px-1.5 py-0.5">ESC</kbd>
        </div>

        <div className="max-h-80 overflow-y-auto">
          {filteredCommands.length > 0 && (
            <div className="p-2">
              <div className="font-mono text-[9px] text-mc-dim tracking-widest uppercase px-2 py-1">Commands</div>
              {filteredCommands.map((cmd) => (
                <button
                  key={cmd.key}
                  onClick={() => handleSelect(cmd)}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded hover:bg-mc-surface text-left cursor-pointer bg-transparent border-none transition-colors"
                >
                  <span className="text-sm opacity-50">{cmd.icon}</span>
                  <span className="text-xs text-gray-200">{cmd.label}</span>
                  <span className="font-mono text-[10px] text-mc-dim ml-auto">{cmd.key}</span>
                </button>
              ))}
            </div>
          )}

          {results.length > 0 && (
            <div className="p-2">
              <div className="font-mono text-[9px] text-mc-dim tracking-widest uppercase px-2 py-1">Results</div>
              {results.map((r) => (
                <div
                  key={`${r.type}-${r.id}`}
                  className="flex items-center gap-3 px-3 py-2 rounded hover:bg-mc-surface transition-colors"
                >
                  <span className="text-sm opacity-50">{typeIcons[r.type] || '·'}</span>
                  <div className="flex-1 min-w-0">
                    <span className="text-xs text-gray-200 truncate block">{r.title}</span>
                    <span className="font-mono text-[9px] text-mc-dim">{r.type}</span>
                  </div>
                  {r.status && <Badge color="#ffffff08" textColor="#555">{r.status}</Badge>}
                </div>
              ))}
            </div>
          )}

          {query && !query.startsWith('/') && results.length === 0 && !searching && (
            <div className="text-xs text-mc-dim text-center py-6">No results found</div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Connection status indicator ──────────────────────────

function ConnectionBar({ health }: { health: api.HealthStatus | null }) {
  if (!health) return null;
  const ok = health.status === 'ok';
  return (
    <div className="flex items-center gap-4 font-mono text-[10px] text-mc-dim">
      <span className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: ok ? '#00ffc8' : '#ff4444' }} />
        DB {health.database}
      </span>
      <span>LLM: {health.llm_provider}</span>
      <span>TG: {health.telegram}</span>
    </div>
  );
}

// ─── Main Dashboard ───────────────────────────────────────

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
      const [p, a, t, i, r, h, hab, g, j, ap] = await Promise.all([
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
      setError(null);
    } catch (e: any) {
      setError(e.message || 'Failed to connect to backend');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Auto-refresh every 30s
  useEffect(() => { const i = setInterval(loadData, 30000); return () => clearInterval(i); }, [loadData]);

  // WebSocket for live updates
  useEffect(() => {
    const ws = api.connectWebSocket((event) => {
      if (event.type.startsWith('agent.') || event.type.startsWith('task.') ||
          event.type.startsWith('idea.') || event.type.startsWith('approval.') ||
          event.type.startsWith('journal.') || event.type.startsWith('goal.')) {
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
          <div className="w-3 h-3 rounded-full bg-mc-accent animate-pulse-glow mx-auto mb-4" />
          <div className="font-mono text-xs text-mc-muted tracking-widest uppercase">Connecting to Mission Control...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-mc-bg">
      {/* Header */}
      <header className="px-8 py-4 border-b border-mc-border bg-[#0a0a12] flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-2.5 h-2.5 rounded-full bg-mc-accent" style={{ boxShadow: '0 0 12px #00ffc880' }} />
            <h1 className="font-mono text-base font-bold text-mc-text tracking-widest uppercase m-0">Mission Control</h1>
          </div>
          <span className="font-mono text-[11px] text-mc-dim">v0.2</span>
          <ConnectionBar health={healthStatus} />
          <button
            onClick={() => setShowCommandPalette(true)}
            className="flex items-center gap-2 px-2.5 py-1 bg-mc-surface border border-mc-border rounded text-mc-dim hover:border-mc-accent/30 hover:text-mc-muted transition-colors cursor-pointer"
          >
            <span className="text-[11px] font-mono">Search...</span>
            <kbd className="text-[9px] border border-mc-border rounded px-1 py-0.5">⌘K</kbd>
          </button>
          {error && <span className="font-mono text-[11px] text-mc-red">{error}</span>}
        </div>

        <div className="flex items-center gap-6">
          <div className="flex gap-5">
            {[
              { label: 'PROJECTS', value: activeProjects, color: '#00ffc8' },
              { label: 'AGENTS', value: `${runningAgents}/${agentsList.length}`, color: runningAgents > 0 ? '#00ffc8' : '#555' },
              { label: 'TASKS', value: openTasks, color: openTasks > 5 ? '#ff4444' : '#ffd166' },
              { label: 'HABITS', value: `${todayHabits}/${habitsList.length}`, color: todayHabits === habitsList.length && habitsList.length > 0 ? '#00ffc8' : '#ffd166' },
              { label: 'GOALS', value: activeGoals, color: '#a78bfa' },
            ].map((s) => (
              <div key={s.label} className="text-center">
                <div className="font-mono text-base font-bold" style={{ color: s.color }}>{s.value}</div>
                <div className="font-mono text-[9px] text-mc-dim tracking-widest">{s.label}</div>
              </div>
            ))}
          </div>
          <div className="font-mono text-xs text-mc-dim">
            {now.toLocaleTimeString('en-US', { hour12: false })}
          </div>
        </div>
      </header>

      {/* Main Grid */}
      <div className="px-8 py-6 grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-[1600px] mx-auto">

        {/* Approval queue - full width, only shows when there are pending approvals */}
        {approvalsList.length > 0 && (
          <div className="lg:col-span-3">
            <ApprovalsPanel approvals={approvalsList} onApprove={handleApprove} onReject={handleReject} />
          </div>
        )}

        {/* Projects - full width */}
        <div className="lg:col-span-3">
          <SectionHeader icon="◆" title="Projects" count={projectsList.length} />
          <ProjectsPanel projects={projectsList} />
        </div>

        {/* Agents - full width */}
        <div className="lg:col-span-3">
          <SectionHeader icon="⚡" title="Agents" count={agentsList.length} />
          <AgentsPanel agents={agentsList} projects={projectsList} onToggle={toggleAgent} />
        </div>

        {/* Column 1: Tasks */}
        <div>
          <SectionHeader icon="◻" title="Tasks" count={openTasks} onAdd={() => setShowTaskInput(true)} />
          <TasksPanel
            tasks={tasksList} projects={projectsList} onToggle={toggleTask}
            onAdd={addTask} showInput={showTaskInput} setShowInput={setShowTaskInput} onDelete={deleteTask}
          />
        </div>

        {/* Column 2: Habits + Goals */}
        <div className="flex flex-col gap-6">
          <div>
            <SectionHeader icon="↻" title="Habits" count={habitsList.length} onAdd={() => setShowHabitInput(true)} />
            <HabitsPanel
              habits={habitsList} onToggle={toggleHabit}
              onAdd={addHabit} showInput={showHabitInput} setShowInput={setShowHabitInput}
            />
          </div>
          <div>
            <SectionHeader icon="◎" title="Goals" count={activeGoals} onAdd={() => setShowGoalInput(true)} />
            <GoalsPanel goals={goalsList} onAdd={addGoal} showInput={showGoalInput} setShowInput={setShowGoalInput} />
          </div>
        </div>

        {/* Column 3: Journal + Ideas + Reading */}
        <div className="flex flex-col gap-6">
          <div>
            <SectionHeader icon="✎" title="Journal" count={journalList.length} onAdd={() => setShowJournalInput(true)} />
            <JournalPanel
              entries={journalList} onAdd={addJournal}
              showInput={showJournalInput} setShowInput={setShowJournalInput} onDelete={deleteJournal}
            />
          </div>
          <div>
            <SectionHeader icon="✦" title="Ideas" count={ideasList.length} onAdd={() => setShowIdeaInput(true)} />
            <IdeasPanel ideas={ideasList} onAdd={addIdea} showInput={showIdeaInput} setShowInput={setShowIdeaInput} onDelete={deleteIdea} />
          </div>
          <div>
            <SectionHeader icon="▤" title="Reading List" count={readingList.filter((r) => !r.is_read).length} onAdd={() => setShowReadingInput(true)} />
            <ReadingPanel
              items={readingList} onToggle={toggleReading}
              onAdd={addReading} showInput={showReadingInput} setShowInput={setShowReadingInput} onDelete={deleteReading}
            />
          </div>
        </div>

        {/* Agent Cost Summary - full width */}
        {agentsList.length > 0 && (
          <div className="lg:col-span-3">
            <SectionHeader icon="$" title="Agent Costs" count={agentsList.length} />
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
              {agentsList.map((a) => {
                const totalCost = a.recent_runs.reduce((sum, r) => sum + (r.cost_usd || 0), 0);
                return (
                  <div key={a.id} className="bg-mc-surface rounded px-3.5 py-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] text-gray-300 truncate">{a.name}</span>
                      <span className="font-mono text-[11px] font-bold" style={{ color: totalCost > 0.1 ? '#ffd166' : '#00ffc8' }}>
                        ${totalCost.toFixed(3)}
                      </span>
                    </div>
                    <div className="font-mono text-[9px] text-mc-dim mt-0.5">
                      {a.recent_runs.length} recent runs · {a.model}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Command Palette */}
      <CommandPalette
        open={showCommandPalette}
        onClose={() => setShowCommandPalette(false)}
        onAction={handleCommandAction}
      />
    </div>
  );
}
