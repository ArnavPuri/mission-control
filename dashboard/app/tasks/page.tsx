'use client';

import { Suspense, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { clsx } from 'clsx';
import { GitPullRequest, Plus, Search, Settings2 } from 'lucide-react';
import * as api from '../lib/api';
import { useWorkspace } from '../components/workspace';
import {
  Avatar, Badge, Button, IconButton, InlineInput, PageHeader, PriorityIcon, Spinner, TaskStatusIcon,
  taskStatusLabel,
} from '../components/shared';
import { DueBadge } from '../components/schedule';

type Filter = 'all' | 'mine' | 'agents' | 'leads';

const COLUMNS: api.Task['status'][] = ['todo', 'in_progress', 'blocked', 'done'];
const PRIORITY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
const DONE_WINDOW_DAYS = 14;

function TaskCard({ task, project, onOpen, onDragStart }: {
  task: api.Task; project?: api.Project; onOpen: () => void; onDragStart: (e: React.DragEvent) => void;
}) {
  const lead = task.tags.includes('lead');
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onClick={onOpen}
      className="group rounded-lg bg-mc-panel ring-1 ring-mc-line shadow-card hover:ring-mc-line-strong hover:shadow-card-hover px-3 py-2.5 cursor-pointer transition-all active:cursor-grabbing"
    >
      <p className={clsx('text-sm leading-snug line-clamp-3', task.status === 'done' ? 'text-mc-muted' : 'text-mc-text')}>{task.text}</p>
      <div className="flex items-center gap-2 mt-2.5 min-h-5">
        <PriorityIcon priority={task.priority} />
        {project && (
          <span className="flex items-center gap-1 text-2xs text-mc-muted min-w-0">
            <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: project.color }} />
            <span className="truncate max-w-[110px]">{project.name}</span>
          </span>
        )}
        {lead && <Badge variant="purple">lead</Badge>}
        {task.github_issue && <GitPullRequest size={12} className="text-mc-dim" aria-label="GitHub issue" />}
        <DueBadge task={task} />
        <span className="flex-1" />
        {task.assigned_agent_name && (
          <span title={task.assigned_agent_name}><Avatar name={task.assigned_agent_name} size={18} /></span>
        )}
      </div>
    </div>
  );
}

function Board() {
  const params = useSearchParams();
  const projectId = params.get('project');
  const { loaded, tasks, projects, refresh, openTask, openProject } = useWorkspace();
  const [filter, setFilter] = useState<Filter>('all');
  const [query, setQuery] = useState('');
  const [adding, setAdding] = useState(false);
  const [dragOver, setDragOver] = useState<string | null>(null);

  const project = projects.find((p) => p.id === projectId);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const cutoff = Date.now() - DONE_WINDOW_DAYS * 86400000;
    return tasks.filter((t) => {
      if (projectId && t.project_id !== projectId) return false;
      const lead = t.tags.includes('lead');
      if (filter === 'leads' ? !lead : lead) return false;
      if (filter === 'mine' && t.assigned_agent_id) return false;
      if (filter === 'agents' && !t.assigned_agent_id && !t.github_issue) return false;
      if (q && !t.text.toLowerCase().includes(q)) return false;
      if (t.status === 'done') return !!t.completed_at && new Date(t.completed_at).getTime() > cutoff;
      return true;
    });
  }, [tasks, projectId, filter, query]);

  const byColumn = (status: api.Task['status']) => {
    const list = visible.filter((t) => t.status === status);
    return status === 'done'
      ? list.sort((a, b) => new Date(b.completed_at!).getTime() - new Date(a.completed_at!).getTime())
      : list.sort((a, b) => (PRIORITY_ORDER[a.priority] ?? 9) - (PRIORITY_ORDER[b.priority] ?? 9));
  };

  const moveTo = async (status: api.Task['status'], e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(null);
    const id = e.dataTransfer.getData('text/task-id');
    const task = tasks.find((t) => t.id === id);
    if (!task || task.status === status) return;
    await api.tasks.update(id, { status });
    refresh();
  };

  const create = async (text: string) => {
    await api.tasks.create({ text, project_id: projectId ?? undefined, tags: filter === 'leads' ? ['lead'] : [] });
    setAdding(false);
    refresh();
  };

  const filters: [Filter, string][] = [['all', 'All'], ['mine', 'Mine'], ['agents', 'Delegated'], ['leads', 'Leads']];
  const openCount = visible.filter((t) => t.status !== 'done').length;

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)] md:h-screen">
      <PageHeader
        title={project ? (
          <span className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: project.color }} />
            {project.name}
          </span>
        ) : 'Tasks'}
        subtitle={project?.description || `${openCount} open${project?.github_repo ? ` · ${project.github_repo}` : ''}`}
        actions={(
          <>
            {project && <IconButton label="Project settings" icon={Settings2} onClick={() => openProject(project)} />}
            <Button variant="primary" icon={Plus} onClick={() => setAdding(true)}>New task</Button>
          </>
        )}
      >
        <div className="max-w-[1400px] mx-auto px-4 sm:px-8 pb-3 flex flex-wrap items-center gap-2">
          <div className="inline-flex p-0.5 rounded-lg bg-mc-subtle ring-1 ring-inset ring-mc-line">
            {filters.map(([key, label]) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={clsx(
                  'h-7 px-3 rounded-md text-xs font-medium transition-colors cursor-pointer',
                  filter === key ? 'bg-mc-panel text-mc-text shadow-card ring-1 ring-mc-line' : 'text-mc-muted hover:text-mc-text',
                )}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="relative w-full sm:w-64">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-mc-dim" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Filter tasks"
              className="h-8 w-full rounded-lg bg-mc-panel pl-8 pr-2.5 text-sm text-mc-text ring-1 ring-inset ring-mc-line placeholder:text-mc-dim outline-none focus:ring-2 focus:ring-mc-accent/50"
            />
          </div>
        </div>
      </PageHeader>

      {!loaded ? (
        <div className="flex-1 flex items-center justify-center"><Spinner size={20} /></div>
      ) : (
        <div className="flex-1 min-h-0 overflow-x-auto">
          <div className="h-full max-w-[1400px] mx-auto px-4 sm:px-8 py-5 grid grid-flow-col auto-cols-[minmax(260px,1fr)] gap-4">
            {COLUMNS.map((status) => {
              const list = byColumn(status);
              return (
                <div
                  key={status}
                  onDragOver={(e) => { e.preventDefault(); setDragOver(status); }}
                  onDragLeave={() => setDragOver((s) => (s === status ? null : s))}
                  onDrop={(e) => moveTo(status, e)}
                  className={clsx(
                    'flex flex-col min-h-0 rounded-xl p-2 transition-colors',
                    dragOver === status ? 'bg-mc-accent/5 ring-1 ring-mc-accent/30' : 'bg-mc-subtle/60',
                  )}
                >
                  <div className="flex items-center gap-2 px-1.5 h-8 mb-1">
                    <TaskStatusIcon status={status} size={14} />
                    <span className="text-sm font-medium text-mc-text">{taskStatusLabel(status)}</span>
                    <span className="text-xs text-mc-dim tabular-nums">{list.length}</span>
                    {status === 'done' && <span className="text-2xs text-mc-dim">· last {DONE_WINDOW_DAYS} days</span>}
                    <span className="flex-1" />
                    {status === 'todo' && <IconButton label="Add task" icon={Plus} onClick={() => setAdding(true)} />}
                  </div>
                  {status === 'todo' && adding && (
                    <div className="px-0.5"><InlineInput placeholder="Task title" onSubmit={create} onCancel={() => setAdding(false)} /></div>
                  )}
                  <div className="flex-1 overflow-y-auto flex flex-col gap-2 p-0.5">
                    {list.map((t) => (
                      <TaskCard
                        key={t.id}
                        task={t}
                        project={projects.find((p) => p.id === t.project_id)}
                        onOpen={() => openTask(t.id)}
                        onDragStart={(e) => e.dataTransfer.setData('text/task-id', t.id)}
                      />
                    ))}
                    {list.length === 0 && (
                      <p className="text-xs text-mc-dim text-center py-6">
                        {status === 'blocked' ? 'Nothing waiting on you' : 'No tasks'}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default function TasksPage() {
  return (
    <Suspense fallback={<div className="py-24 flex justify-center"><Spinner size={20} /></div>}>
      <Board />
    </Suspense>
  );
}
