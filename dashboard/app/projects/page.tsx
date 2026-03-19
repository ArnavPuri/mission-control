'use client';

import { useState, useEffect, useCallback } from 'react';
import * as api from '../lib/api';
import * as Progress from '@radix-ui/react-progress';
import * as Tooltip from '@radix-ui/react-tooltip';
import {
  FolderOpen, ListTodo, Zap, Lightbulb, StickyNote, BookOpen,
  Plus, ChevronRight, ExternalLink, Loader2,
} from 'lucide-react';
import { clsx } from 'clsx';
import { Card, Badge, SectionHeader, StatusIndicator, EmptyState, InlineInput } from '../components/shared';

export default function ProjectsPage() {
  const [projects, setProjects] = useState<api.Project[]>([]);
  const [tasks, setTasks] = useState<api.Task[]>([]);
  const [ideas, setIdeas] = useState<api.Idea[]>([]);
  const [agents, setAgents] = useState<api.Agent[]>([]);
  const [notes, setNotes] = useState<api.Note[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [showCreateInput, setShowCreateInput] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [p, t, i, a, g, n] = await Promise.all([
        api.projects.list(),
        api.tasks.list(),
        api.ideas.list(),
        api.agents.list(),
        api.notes.list().catch(() => []),
      ]);
      setProjects(p); setTasks(t); setIdeas(i); setAgents(a); setNotes(n);
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const createProject = async (name: string) => {
    await api.projects.create({ name, description: '' });
    setShowCreateInput(false);
    loadData();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-mc-bg dark:bg-gray-950 flex items-center justify-center">
        <Loader2 size={24} className="text-mc-accent animate-spin" />
      </div>
    );
  }

  const selected = selectedProject ? projects.find((p) => p.id === selectedProject) : null;
  const projectTasks = selectedProject ? tasks.filter((t) => t.project_id === selectedProject) : [];
  const projectIdeas = selectedProject ? ideas.filter((i) => i.project_id === selectedProject) : [];
  const projectAgents = selectedProject ? agents.filter((a) => a.project_id === selectedProject) : [];
  const projectNotes = selectedProject ? notes.filter((n) => n.project_id === selectedProject) : [];

  return (
    <Tooltip.Provider delayDuration={200}>
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

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Project List */}
            <div className="flex flex-col gap-3">
              <h2 className="text-xs font-semibold text-mc-dim uppercase tracking-wide">All Projects</h2>
              {projects.map((p) => {
                const isSelected = selectedProject === p.id;
                return (
                  <button
                    key={p.id}
                    onClick={() => setSelectedProject(isSelected ? null : p.id)}
                    className={clsx(
                      'w-full text-left p-4 rounded-xl border transition-all cursor-pointer bg-white dark:bg-gray-900',
                      isSelected
                        ? 'border-mc-accent shadow-md ring-2 ring-mc-accent/10'
                        : 'border-mc-border dark:border-gray-800 hover:shadow-card-hover'
                    )}
                    style={{ borderLeftWidth: 3, borderLeftColor: p.color }}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <StatusIndicator status={p.status} />
                      <span className="text-sm font-semibold text-mc-text dark:text-gray-100 truncate">{p.name}</span>
                    </div>
                    <p className="text-xs text-mc-muted dark:text-gray-500 truncate mb-2">{p.description}</p>
                    <div className="flex items-center gap-3 text-[11px] text-mc-dim">
                      <span>{p.task_count} tasks</span>
                      <span>{p.agent_count} agents</span>
                      <Badge variant={p.status === 'active' ? 'success' : 'warning'}>{p.status}</Badge>
                    </div>
                  </button>
                );
              })}
              {projects.length === 0 && <EmptyState icon={FolderOpen} message="No projects yet" />}
            </div>

            {/* Project Dashboard */}
            <div className="lg:col-span-2">
              {selected ? (
                <div className="flex flex-col gap-4">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-3 h-3 rounded-full" style={{ background: selected.color }} />
                    <h2 className="text-lg font-bold text-mc-text dark:text-gray-100">{selected.name}</h2>
                    <Badge variant={selected.status === 'active' ? 'success' : 'warning'}>{selected.status}</Badge>
                    {selected.url && (
                      <a href={selected.url} target="_blank" rel="noopener noreferrer" className="text-mc-accent hover:underline text-xs flex items-center gap-1">
                        <ExternalLink size={12} /> Link
                      </a>
                    )}
                  </div>
                  {selected.description && (
                    <p className="text-sm text-mc-muted dark:text-gray-400">{selected.description}</p>
                  )}

                  {/* Stats */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {[
                      { label: 'Tasks', value: projectTasks.length, icon: ListTodo },
                      { label: 'Ideas', value: projectIdeas.length, icon: Lightbulb },
                      { label: 'Agents', value: projectAgents.length, icon: Zap },
                      { label: 'Notes', value: projectNotes.length, icon: StickyNote },
                    ].map((s) => (
                      <Card key={s.label} className="p-3 text-center">
                        <s.icon size={16} className="text-mc-muted mx-auto mb-1" />
                        <div className="text-lg font-bold text-mc-text dark:text-gray-100">{s.value}</div>
                        <div className="text-[11px] text-mc-dim">{s.label}</div>
                      </Card>
                    ))}
                  </div>

                  {/* Tasks */}
                  <Card className="p-4">
                    <SectionHeader icon={ListTodo} title="Tasks" count={projectTasks.length} />
                    <div className="flex flex-col gap-1.5">
                      {projectTasks.slice(0, 10).map((t) => (
                        <div key={t.id} className="flex items-center gap-2 py-1.5">
                          <span className={clsx('w-2 h-2 rounded-full shrink-0', t.status === 'done' ? 'bg-emerald-500' : t.priority === 'critical' ? 'bg-red-500' : t.priority === 'high' ? 'bg-amber-500' : 'bg-gray-300')} />
                          <span className={clsx('text-sm flex-1 truncate', t.status === 'done' ? 'text-mc-dim line-through' : 'text-mc-text dark:text-gray-200')}>{t.text}</span>
                          <Badge variant={t.status === 'done' ? 'success' : 'default'}>{t.status}</Badge>
                        </div>
                      ))}
                      {projectTasks.length === 0 && <span className="text-xs text-mc-dim py-2">No tasks linked</span>}
                    </div>
                  </Card>

                  {/* Agents */}
                  {projectAgents.length > 0 && (
                    <Card className="p-4">
                      <SectionHeader icon={Zap} title="Agents" count={projectAgents.length} />
                      <div className="flex flex-col gap-2">
                        {projectAgents.map((a) => (
                          <div key={a.id} className="flex items-center gap-3 py-1.5">
                            <StatusIndicator status={a.status} />
                            <span className="text-sm text-mc-text dark:text-gray-200 flex-1">{a.name}</span>
                            <span className="text-[11px] text-mc-dim font-mono">{a.model}</span>
                          </div>
                        ))}
                      </div>
                    </Card>
                  )}

                  {/* Notes */}
                  {projectNotes.length > 0 && (
                    <Card className="p-4">
                      <SectionHeader icon={BookOpen} title="Notes" count={projectNotes.length} />
                      <div className="flex flex-col gap-2">
                        {projectNotes.map((n) => (
                          <div key={n.id} className="flex items-center gap-2 py-1.5">
                            <ChevronRight size={12} className="text-mc-dim shrink-0" />
                            <span className="text-sm text-mc-text dark:text-gray-200 flex-1 truncate">{n.title}</span>
                            <span className="text-[11px] text-mc-dim">{new Date(n.updated_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span>
                          </div>
                        ))}
                      </div>
                    </Card>
                  )}
                </div>
              ) : (
                <div className="flex items-center justify-center h-64">
                  <EmptyState icon={FolderOpen} message="Select a project to see its dashboard" />
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </Tooltip.Provider>
  );
}
