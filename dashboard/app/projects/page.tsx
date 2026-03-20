'use client';

import { useState, useEffect, useCallback } from 'react';
import * as api from '../lib/api';
import {
  FolderOpen, Plus, ExternalLink, Loader2, Globe, Check,
  Megaphone, MessageSquare, Lightbulb, ListTodo, ChevronRight,
} from 'lucide-react';
import { clsx } from 'clsx';
import { Card, Badge, StatusIndicator, EmptyState, InlineInput } from '../components/shared';

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

        {/* Tabs */}
        <div className="flex items-center gap-6 mt-4 border-b border-mc-border dark:border-gray-800">
          {tabs.map((tab) => (
            <button
              key={tab.key}
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
      <div className="flex-1 overflow-y-auto p-5 pt-3 max-h-[min(400px,50vh)]">
        {activeTab === 'tasks' && (
          <div className="flex flex-col gap-0.5">
            {[...openTasks, ...doneTasks].map((task) => (
              <div key={task.id} className="flex items-start gap-3 py-2.5 border-b border-mc-border/40 dark:border-gray-800/40 last:border-0">
                <button
                  onClick={() => onToggleTask(task)}
                  className={clsx(
                    'mt-0.5 w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 transition-colors cursor-pointer',
                    task.status === 'done'
                      ? 'bg-emerald-500 border-emerald-500 text-white'
                      : 'border-gray-300 dark:border-gray-600 hover:border-emerald-400'
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
                <Lightbulb size={14} className="text-amber-400 mt-0.5 shrink-0" />
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
                      <a href={sig.source_url} target="_blank" rel="noopener noreferrer" className="text-mc-accent shrink-0">
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
                      <a href={c.posted_url} target="_blank" rel="noopener noreferrer" className="text-mc-accent shrink-0">
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

export default function ProjectsPage() {
  const [projects, setProjects] = useState<api.Project[]>([]);
  const [tasks, setTasks] = useState<api.Task[]>([]);
  const [ideas, setIdeas] = useState<api.Idea[]>([]);
  const [signals, setSignals] = useState<api.MarketingSignal[]>([]);
  const [content, setContent] = useState<api.MarketingContent[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateInput, setShowCreateInput] = useState(false);

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

  const createProject = async (name: string) => {
    await api.projects.create({ name, description: '' });
    setShowCreateInput(false);
    loadData();
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
            onClick={() => setShowCreateInput(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-mc-accent text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors cursor-pointer"
          >
            <Plus size={14} />
            <span className="hidden sm:inline">New Project</span>
          </button>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {showCreateInput && (
          <div className="mb-6">
            <InlineInput placeholder="Project name..." onSubmit={createProject} onCancel={() => setShowCreateInput(false)} />
          </div>
        )}

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
