'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import * as api from '../lib/api';
import {
  FolderOpen, Plus, ExternalLink, Loader2, Globe, Check,
  Megaphone, MessageSquare, Lightbulb,
  X, Sparkles, RefreshCw,
} from 'lucide-react';
import { clsx } from 'clsx';
import { Card, Badge, EmptyState } from '../components/shared';

type ProjectTab = 'tasks' | 'ideas' | 'feedback';

function ProjectCard({
  project,
  tasks,
  ideas,
  signals,
  content,
  onToggleTask,
  onAddTask,
  onAddIdea,
}: {
  project: api.Project;
  tasks: api.Task[];
  ideas: api.Idea[];
  signals: api.MarketingSignal[];
  content: api.MarketingContent[];
  onToggleTask: (task: api.Task) => void;
  onAddTask: (text: string) => void;
  onAddIdea: (text: string) => void;
}) {
  const [activeTab, setActiveTab] = useState<ProjectTab>('tasks');
  const [newTaskText, setNewTaskText] = useState('');
  const [newIdeaText, setNewIdeaText] = useState('');

  const openTasks = tasks.filter((t) => t.status !== 'done');
  const doneTasks = tasks.filter((t) => t.status === 'done');

  const tabs: { key: ProjectTab; label: string; count: number }[] = [
    { key: 'tasks', label: 'Tasks', count: tasks.length },
    { key: 'ideas', label: 'Ideas', count: ideas.length },
    { key: 'feedback', label: 'Feedback', count: signals.length + content.length },
  ];

  const statusLabel = project.status.charAt(0).toUpperCase() + project.status.slice(1);

  const handleAddTask = () => {
    if (newTaskText.trim()) {
      onAddTask(newTaskText.trim());
      setNewTaskText('');
    }
  };

  const handleAddIdea = () => {
    if (newIdeaText.trim()) {
      onAddIdea(newIdeaText.trim());
      setNewIdeaText('');
    }
  };

  return (
    <Card className="flex flex-col overflow-hidden">
      {/* Header */}
      <div className="p-5 pb-0">
        <div className="flex items-start justify-between mb-1">
          <div>
            <h2 className="text-lg font-bold text-mc-text dark:text-gray-100">{project.name}</h2>
            <span className="text-xs text-mc-muted dark:text-gray-500">{statusLabel}</span>
          </div>
          <div className="text-right text-xs text-mc-muted dark:text-gray-500 space-y-0.5">
            <div>{openTasks.length} open</div>
            <div>{ideas.length} ideas</div>
          </div>
        </div>

        {/* Website & Description */}
        {project.url && (
          <a
            href={project.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-mc-accent hover:underline mt-1"
          >
            <Globe size={11} />
            {project.url.replace(/^https?:\/\//, '').replace(/\/$/, '')}
          </a>
        )}
        {project.description && (
          <p className="text-xs text-mc-muted dark:text-gray-400 mt-2 line-clamp-2">{project.description}</p>
        )}

        {/* Brand Info */}
        {(() => {
          const meta = project.metadata || {};
          const brand = meta.brand as { tagline?: string; offering?: string; brand_voice?: string; tone_keywords?: string[]; brand_colors?: string[] } | undefined;
          const enrichStatus = meta.enrichment_status as string | undefined;

          if (enrichStatus === 'pending') {
            return (
              <div className="flex items-center gap-2 mt-2 text-xs text-mc-muted dark:text-gray-500" role="status">
                <Loader2 size={12} className="animate-spin" />
                <span>Fetching brand info...</span>
              </div>
            );
          }

          if (enrichStatus === 'failed') {
            return (
              <div className="flex items-center gap-2 mt-2 text-xs text-mc-muted dark:text-gray-500">
                <span>Brand fetch failed.</span>
                <button
                  onClick={() => api.projects.enrich(project.id)}
                  className="inline-flex items-center gap-1 text-mc-accent hover:underline cursor-pointer"
                  aria-label={`Retry brand fetch for ${project.name}`}
                >
                  <RefreshCw size={10} /> Retry
                </button>
              </div>
            );
          }

          if (brand) {
            return (
              <div className="mt-2 space-y-1.5">
                {brand.tagline && (
                  <p className="text-xs font-medium text-mc-text dark:text-gray-300 italic">&ldquo;{brand.tagline}&rdquo;</p>
                )}
                {brand.brand_voice && (
                  <p className="text-[11px] text-mc-muted dark:text-gray-500">
                    <span className="font-medium">Voice:</span> {brand.brand_voice}
                  </p>
                )}
                {brand.tone_keywords && brand.tone_keywords.length > 0 && (
                  <div className="flex gap-1 flex-wrap">
                    {brand.tone_keywords.map((kw) => (
                      <span key={kw} className="text-[10px] px-1.5 py-0.5 rounded-full bg-mc-accent/10 text-mc-accent dark:bg-mc-accent/20">{kw}</span>
                    ))}
                  </div>
                )}
                {brand.brand_colors && brand.brand_colors.length > 0 && (
                  <div className="flex items-center gap-1">
                    {brand.brand_colors.slice(0, 5).map((c) => (
                      <div key={c} className="w-4 h-4 rounded-full border border-mc-border dark:border-gray-700" style={{ backgroundColor: c }} title={c} />
                    ))}
                  </div>
                )}
              </div>
            );
          }

          return null;
        })()}

        {/* Tabs */}
        <div role="tablist" aria-label={`${project.name} sections`} className="flex items-center gap-6 mt-4 border-b border-mc-border dark:border-gray-800">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              role="tab"
              aria-selected={activeTab === tab.key}
              aria-controls={`${project.id}-panel-${tab.key}`}
              id={`${project.id}-tab-${tab.key}`}
              onClick={() => setActiveTab(tab.key)}
              className={clsx(
                'pb-2.5 text-sm font-medium transition-colors relative cursor-pointer flex items-center gap-1.5',
                activeTab === tab.key
                  ? 'text-mc-text dark:text-gray-100'
                  : 'text-mc-muted dark:text-gray-500 hover:text-mc-text dark:hover:text-gray-300'
              )}
            >
              {tab.label}
              <span className={clsx(
                'text-xs',
                activeTab === tab.key ? 'text-mc-dim' : 'text-mc-dim/60'
              )}>
                {tab.count}
              </span>
              {activeTab === tab.key && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-mc-accent rounded-t" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div
        role="tabpanel"
        id={`${project.id}-panel-${activeTab}`}
        aria-labelledby={`${project.id}-tab-${activeTab}`}
        className="flex-1 overflow-y-auto p-5 pt-3 max-h-[min(400px,50vh)]"
      >
        {activeTab === 'tasks' && (
          <div className="flex flex-col gap-0.5">
            {[...openTasks, ...doneTasks].map((task) => (
              <div key={task.id} className="flex items-start gap-3 py-2.5 border-b border-mc-border/40 dark:border-gray-800/40 last:border-0">
                <button
                  role="checkbox"
                  aria-checked={task.status === 'done'}
                  aria-label={`Mark "${task.text}" as ${task.status === 'done' ? 'incomplete' : 'complete'}`}
                  onClick={() => onToggleTask(task)}
                  className={clsx(
                    'mt-0.5 w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 transition-colors cursor-pointer',
                    task.status === 'done'
                      ? 'bg-mc-green border-mc-green text-white'
                      : 'border-mc-border dark:border-gray-600 hover:border-mc-green'
                  )}
                >
                  {task.status === 'done' && <Check size={12} strokeWidth={3} />}
                </button>
                <span className={clsx(
                  'text-sm leading-relaxed',
                  task.status === 'done'
                    ? 'text-mc-dim line-through'
                    : 'text-mc-text dark:text-gray-200'
                )}>
                  {task.text}
                </span>
              </div>
            ))}
            {tasks.length === 0 && (
              <span className="text-xs text-mc-dim py-4 text-center block">No tasks yet</span>
            )}
          </div>
        )}

        {activeTab === 'ideas' && (
          <div className="flex flex-col gap-0.5">
            {ideas.map((idea) => (
              <div key={idea.id} className="flex items-start gap-3 py-2.5 border-b border-mc-border/40 dark:border-gray-800/40 last:border-0">
                <Lightbulb size={14} className="text-mc-yellow mt-0.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="text-sm text-mc-text dark:text-gray-200">{idea.text}</span>
                  {idea.tags.length > 0 && (
                    <div className="flex gap-1 mt-1 flex-wrap">
                      {idea.tags.map((tag) => (
                        <Badge key={tag} variant="purple">{tag}</Badge>
                      ))}
                    </div>
                  )}
                </div>
                {idea.score != null && idea.score > 0 && (
                  <span className="text-[11px] text-mc-dim shrink-0">{Math.round(idea.score * 100)}%</span>
                )}
              </div>
            ))}
            {ideas.length === 0 && (
              <span className="text-xs text-mc-dim py-4 text-center block">No ideas yet</span>
            )}
          </div>
        )}

        {activeTab === 'feedback' && (
          <div className="flex flex-col gap-3">
            {/* Marketing Signals */}
            {signals.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-mc-dim uppercase tracking-wide mb-2 flex items-center gap-1.5">
                  <MessageSquare size={12} /> Signals
                </h4>
                {signals.map((sig) => (
                  <div key={sig.id} className="flex items-start gap-3 py-2 border-b border-mc-border/40 dark:border-gray-800/40 last:border-0">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-mc-text dark:text-gray-200">{sig.title}</div>
                      {sig.body && <p className="text-xs text-mc-muted dark:text-gray-400 mt-0.5 line-clamp-2">{sig.body}</p>}
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant={sig.status === 'acted_on' ? 'success' : sig.status === 'new' ? 'blue' : 'default'}>
                          {sig.status}
                        </Badge>
                        <span className="text-[11px] text-mc-dim">{sig.source_type}</span>
                      </div>
                    </div>
                    {sig.source_url && (
                      <a href={sig.source_url} target="_blank" rel="noopener noreferrer" className="text-mc-accent shrink-0" aria-label={`Open source for ${sig.title}`}>
                        <ExternalLink size={12} />
                      </a>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Marketing Content */}
            {content.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-mc-dim uppercase tracking-wide mb-2 flex items-center gap-1.5">
                  <Megaphone size={12} /> Content
                </h4>
                {content.map((c) => (
                  <div key={c.id} className="flex items-start gap-3 py-2 border-b border-mc-border/40 dark:border-gray-800/40 last:border-0">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-mc-text dark:text-gray-200">{c.title}</div>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant={c.status === 'posted' ? 'success' : c.status === 'draft' ? 'default' : 'warning'}>
                          {c.status}
                        </Badge>
                        <span className="text-[11px] text-mc-dim">{c.channel}</span>
                      </div>
                    </div>
                    {c.posted_url && (
                      <a href={c.posted_url} target="_blank" rel="noopener noreferrer" className="text-mc-accent shrink-0" aria-label={`Open ${c.title}`}>
                        <ExternalLink size={12} />
                      </a>
                    )}
                  </div>
                ))}
              </div>
            )}

            {signals.length === 0 && content.length === 0 && (
              <span className="text-xs text-mc-dim py-4 text-center block">No feedback or marketing signals yet</span>
            )}
          </div>
        )}
      </div>

      {/* Bottom input */}
      {activeTab === 'tasks' && (
        <div className="border-t border-mc-border dark:border-gray-800 p-3 flex gap-2">
          <input
            type="text"
            aria-label={`Add task to ${project.name}`}
            value={newTaskText}
            onChange={(e) => setNewTaskText(e.target.value)}
            placeholder="New task..."
            onKeyDown={(e) => { if (e.key === 'Enter') handleAddTask(); }}
            className="flex-1 bg-transparent text-sm text-mc-text dark:text-gray-200 placeholder:text-mc-dim outline-none px-2 py-1.5"
          />
          <button
            onClick={handleAddTask}
            disabled={!newTaskText.trim()}
            className="px-3 py-1.5 text-xs font-medium text-mc-muted dark:text-gray-400 hover:text-mc-accent transition-colors cursor-pointer disabled:opacity-40"
          >
            Add
          </button>
        </div>
      )}
      {activeTab === 'ideas' && (
        <div className="border-t border-mc-border dark:border-gray-800 p-3 flex gap-2">
          <input
            type="text"
            aria-label={`Add idea to ${project.name}`}
            value={newIdeaText}
            onChange={(e) => setNewIdeaText(e.target.value)}
            placeholder="New idea..."
            onKeyDown={(e) => { if (e.key === 'Enter') handleAddIdea(); }}
            className="flex-1 bg-transparent text-sm text-mc-text dark:text-gray-200 placeholder:text-mc-dim outline-none px-2 py-1.5"
          />
          <button
            onClick={handleAddIdea}
            disabled={!newIdeaText.trim()}
            className="px-3 py-1.5 text-xs font-medium text-mc-muted dark:text-gray-400 hover:text-mc-accent transition-colors cursor-pointer disabled:opacity-40"
          >
            Add
          </button>
        </div>
      )}
    </Card>
  );
}

function CreateProjectDialog({
  newName, setNewName, newUrl, setNewUrl, creating, onClose, onCreate,
}: {
  newName: string; setNewName: (v: string) => void;
  newUrl: string; setNewUrl: (v: string) => void;
  creating: boolean; onClose: () => void; onCreate: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);

  // Focus trap + Escape handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { onClose(); return; }
      if (e.key !== 'Tab') return;

      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'input, button, [tabindex]:not([tabindex="-1"])'
      );
      if (!focusable || focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose} role="presentation">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-project-title"
        className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-md mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 id="create-project-title" className="text-lg font-bold text-mc-text dark:text-gray-100">New Project</h2>
          <button onClick={onClose} aria-label="Close dialog" className="text-mc-muted hover:text-mc-text dark:hover:text-gray-300 cursor-pointer">
            <X size={18} />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label htmlFor="project-name" className="block text-xs font-medium text-mc-muted dark:text-gray-400 mb-1.5">Project Name *</label>
            <input
              id="project-name"
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="My Awesome Project"
              autoFocus
              maxLength={200}
              onKeyDown={(e) => { if (e.key === 'Enter' && newName.trim()) onCreate(); }}
              className="w-full px-3 py-2 text-sm bg-mc-bg dark:bg-gray-800 border border-mc-border dark:border-gray-700 rounded-lg text-mc-text dark:text-gray-200 placeholder:text-mc-dim outline-none focus:border-mc-accent focus:ring-1 focus:ring-mc-accent/30"
            />
          </div>
          <div>
            <label htmlFor="project-url" className="block text-xs font-medium text-mc-muted dark:text-gray-400 mb-1.5">
              Website URL
              <span className="ml-1.5 text-mc-dim font-normal">(optional — auto-fetches brand info)</span>
            </label>
            <input
              id="project-url"
              type="url"
              value={newUrl}
              onChange={(e) => setNewUrl(e.target.value)}
              placeholder="https://example.com"
              onKeyDown={(e) => { if (e.key === 'Enter' && newName.trim()) onCreate(); }}
              className="w-full px-3 py-2 text-sm bg-mc-bg dark:bg-gray-800 border border-mc-border dark:border-gray-700 rounded-lg text-mc-text dark:text-gray-200 placeholder:text-mc-dim outline-none focus:border-mc-accent focus:ring-1 focus:ring-mc-accent/30"
            />
            {newUrl.trim() && (
              <p className="text-[11px] text-mc-accent mt-1 flex items-center gap-1">
                <Sparkles size={10} />
                Brand voice, offering, and colors will be auto-detected
              </p>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-mc-muted dark:text-gray-400 hover:text-mc-text dark:hover:text-gray-200 transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={onCreate}
            disabled={!newName.trim() || creating}
            className="flex items-center gap-2 px-4 py-2 bg-mc-accent text-white text-sm font-medium rounded-lg hover:opacity-90 transition-colors cursor-pointer disabled:opacity-50"
          >
            {creating ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
            Create Project
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<api.Project[]>([]);
  const [tasks, setTasks] = useState<api.Task[]>([]);
  const [ideas, setIdeas] = useState<api.Idea[]>([]);
  const [signals, setSignals] = useState<api.MarketingSignal[]>([]);
  const [content, setContent] = useState<api.MarketingContent[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newName, setNewName] = useState('');
  const [newUrl, setNewUrl] = useState('');
  const [creating, setCreating] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [p, t, i, s, c] = await Promise.all([
        api.projects.list(),
        api.tasks.list(),
        api.ideas.list(),
        api.fetchSignals().catch((e) => { console.warn('Failed to fetch signals:', e); return []; }),
        api.fetchContent().catch((e) => { console.warn('Failed to fetch content:', e); return []; }),
      ]);
      setProjects(p); setTasks(t); setIdeas(i); setSignals(s); setContent(c);
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Listen for WebSocket updates to refresh enriched projects (with reconnect)
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let unmounted = false;

    function connect() {
      if (unmounted) return;
      const wsUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/^http/, 'ws') + '/ws';
      ws = new WebSocket(wsUrl);
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'project.updated') {
            loadData();
          }
        } catch {}
      };
      ws.onclose = () => {
        if (!unmounted) reconnectTimer = setTimeout(connect, 5000);
      };
      ws.onerror = () => ws?.close();
    }

    connect();
    return () => {
      unmounted = true;
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [loadData]);

  const createProject = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const data: Record<string, string> = { name: newName.trim(), description: '' };
      if (newUrl.trim()) data.url = newUrl.trim();
      await api.projects.create(data as Partial<api.Project>);
      setShowCreateDialog(false);
      setNewName('');
      setNewUrl('');
      loadData();
    } finally {
      setCreating(false);
    }
  };

  const toggleTask = async (task: api.Task) => {
    const newStatus = task.status === 'done' ? 'todo' : 'done';
    setTasks((prev) => prev.map((t) => t.id === task.id ? { ...t, status: newStatus } : t));
    try {
      await api.tasks.update(task.id, { status: newStatus } as Partial<api.Task>);
    } catch {
      setTasks((prev) => prev.map((t) => t.id === task.id ? { ...t, status: task.status } : t));
    }
  };

  const addTaskToProject = async (projectId: string, text: string) => {
    await api.tasks.create({ text, project_id: projectId } as Partial<api.Task>);
    const updated = await api.tasks.list();
    setTasks(updated);
  };

  const addIdeaToProject = async (projectId: string, text: string) => {
    await api.ideas.create({ text, project_id: projectId } as Partial<api.Idea>);
    const updated = await api.ideas.list();
    setIdeas(updated);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-mc-bg dark:bg-gray-950 flex items-center justify-center">
        <Loader2 size={24} className="text-mc-accent animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-mc-bg dark:bg-gray-950 transition-colors">
      <header className="px-4 sm:px-6 lg:px-8 py-3 bg-white dark:bg-gray-900 border-b border-mc-border dark:border-gray-800 sticky top-0 z-30">
        <div className="max-w-[1600px] mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <FolderOpen size={18} className="text-mc-accent" />
            <h1 className="text-base font-bold text-mc-text dark:text-gray-100">Projects</h1>
            <span className="text-xs text-mc-dim">{projects.length} total</span>
          </div>
          <button
            onClick={() => setShowCreateDialog(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-mc-accent text-white text-sm font-medium rounded-lg hover:bg-mc-accent-hover transition-colors cursor-pointer"
          >
            <Plus size={14} />
            <span className="hidden sm:inline">New Project</span>
          </button>
        </div>
      </header>

      {/* Create Project Dialog */}
      {showCreateDialog && (
        <CreateProjectDialog
          newName={newName}
          setNewName={setNewName}
          newUrl={newUrl}
          setNewUrl={setNewUrl}
          creating={creating}
          onClose={() => setShowCreateDialog(false)}
          onCreate={createProject}
        />
      )}

      <main className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-6">

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {projects.map((project) => {
            const projectTasks = tasks.filter((t) => t.project_id === project.id);
            const projectIdeas = ideas.filter((i) => i.project_id === project.id);
            const projectSignals = signals.filter((s) => s.project_id === project.id);
            const projectContent = content.filter((c) => c.project_id === project.id);

            return (
              <ProjectCard
                key={project.id}
                project={project}
                tasks={projectTasks}
                ideas={projectIdeas}
                signals={projectSignals}
                content={projectContent}
                onToggleTask={toggleTask}
                onAddTask={(text) => addTaskToProject(project.id, text)}
                onAddIdea={(text) => addIdeaToProject(project.id, text)}
              />
            );
          })}
          {projects.length === 0 && (
            <div className="col-span-full">
              <EmptyState icon={FolderOpen} message="No projects yet — create one to get started" />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
