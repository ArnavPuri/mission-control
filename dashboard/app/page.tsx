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
  const [healthStatus, setHealth] = useState<api.HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(new Date());

  const [showTaskInput, setShowTaskInput] = useState(false);
  const [showIdeaInput, setShowIdeaInput] = useState(false);
  const [showReadingInput, setShowReadingInput] = useState(false);

  // Clock
  useEffect(() => { const i = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(i); }, []);

  // Load all data
  const loadData = useCallback(async () => {
    try {
      const [p, a, t, i, r, h] = await Promise.all([
        api.projects.list(),
        api.agents.list(),
        api.tasks.list(),
        api.ideas.list(),
        api.reading.list(),
        api.health.check(),
      ]);
      setProjects(p);
      setAgents(a);
      setTasks(t);
      setIdeas(i);
      setReading(r);
      setHealth(h);
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
      // On any event, refresh the relevant data
      if (event.type.startsWith('agent.')) loadData();
      if (event.type.startsWith('task.')) loadData();
      if (event.type.startsWith('idea.')) loadData();
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

  const addTask = async (text: string) => { await api.tasks.create({ text }); setShowTaskInput(false); loadData(); };
  const addIdea = async (text: string) => { await api.ideas.create({ text }); setShowIdeaInput(false); loadData(); };
  const addReading = async (text: string) => {
    const isUrl = text.startsWith('http');
    await api.reading.create({ title: isUrl ? text : text, url: isUrl ? text : undefined });
    setShowReadingInput(false);
    loadData();
  };

  const deleteTask = async (id: string) => { await api.tasks.delete(id); loadData(); };
  const deleteIdea = async (id: string) => { await api.ideas.delete(id); loadData(); };
  const deleteReading = async (id: string) => { await api.reading.delete(id); loadData(); };

  // --- Stats ---
  const runningAgents = agentsList.filter((a) => a.status === 'running').length;
  const activeProjects = projectsList.filter((p) => p.status === 'active').length;
  const openTasks = tasksList.filter((t) => t.status !== 'done').length;

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
          <span className="font-mono text-[11px] text-mc-dim">v0.1</span>
          <ConnectionBar health={healthStatus} />
          {error && <span className="font-mono text-[11px] text-mc-red">{error}</span>}
        </div>

        <div className="flex items-center gap-6">
          <div className="flex gap-5">
            {[
              { label: 'PROJECTS', value: activeProjects, color: '#00ffc8' },
              { label: 'AGENTS', value: `${runningAgents}/${agentsList.length}`, color: runningAgents > 0 ? '#00ffc8' : '#555' },
              { label: 'TASKS', value: openTasks, color: openTasks > 5 ? '#ff4444' : '#ffd166' },
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
      <div className="px-8 py-6 grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-[1400px] mx-auto">
        {/* Projects - full width */}
        <div className="lg:col-span-2">
          <SectionHeader icon="◆" title="Projects" count={projectsList.length} />
          <ProjectsPanel projects={projectsList} />
        </div>

        {/* Agents - full width */}
        <div className="lg:col-span-2">
          <SectionHeader icon="⚡" title="Agents" count={agentsList.length} />
          <AgentsPanel agents={agentsList} projects={projectsList} onToggle={toggleAgent} />
        </div>

        {/* Tasks - left column */}
        <div>
          <SectionHeader icon="◻" title="Tasks" count={openTasks} onAdd={() => setShowTaskInput(true)} />
          <TasksPanel
            tasks={tasksList} projects={projectsList} onToggle={toggleTask}
            onAdd={addTask} showInput={showTaskInput} setShowInput={setShowTaskInput} onDelete={deleteTask}
          />
        </div>

        {/* Right column: Ideas + Reading */}
        <div className="flex flex-col gap-6">
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
      </div>
    </div>
  );
}
