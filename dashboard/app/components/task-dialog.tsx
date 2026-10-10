'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import {
  ArrowUp, Check, ChevronDown, ExternalLink, FolderOpen, GitPullRequest, Link2, MoreHorizontal, Repeat, Trash2, X,
} from 'lucide-react';
import { clsx } from 'clsx';
import * as api from '../lib/api';
import { Markdown } from './markdown';
import { DuePicker, ReminderPicker, reminderPending } from './schedule';
import {
  Avatar, Badge, Button, PriorityIcon, Spinner, TaskStatusIcon, agentDisplay, taskStatusLabel, textareaClass, timeAgo,
} from './shared';

const STATUSES: api.Task['status'][] = ['todo', 'in_progress', 'blocked', 'done'];
const PRIORITIES: api.Task['priority'][] = ['critical', 'high', 'medium', 'low'];
const RECURRENCES: api.Recurrence[] = ['daily', 'weekdays', 'weekly', 'monthly'];
const REPEAT_LABELS: Record<api.Recurrence, string> = {
  daily: 'Every day', weekdays: 'Every weekday', weekly: 'Every week', monthly: 'Every month',
};

function authorName(author: string, agents: api.Agent[]): string {
  if (author === 'user') return 'You';
  if (author === 'system') return 'System';
  const slug = author.replace(/^agent:/, '');
  return agents.find((a) => a.slug === slug)?.name ?? slug;
}

const menuContent = 'min-w-[200px] max-h-80 overflow-y-auto bg-mc-panel rounded-lg shadow-dropdown p-1 z-[60] animate-fade-up';
const menuItem = 'flex items-center gap-2 h-8 px-2 rounded-md text-sm text-mc-secondary outline-none cursor-pointer data-[highlighted]:bg-mc-hover data-[highlighted]:text-mc-text';

/** A property row in the sheet's side panel: label on the left, a menu trigger on the right. */
function Property({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center min-h-8 gap-2">
      <span className="w-24 flex-shrink-0 text-xs text-mc-muted">{label}</span>
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  );
}

function PropertyTrigger({ children }: { children: React.ReactNode }) {
  return (
    <DropdownMenu.Trigger asChild>
      <button className="max-w-full h-7 inline-flex items-center gap-1.5 px-2 -mx-2 rounded-md text-sm text-mc-text hover:bg-mc-hover cursor-pointer">
        {children}
        <ChevronDown size={12} className="text-mc-dim flex-shrink-0" />
      </button>
    </DropdownMenu.Trigger>
  );
}

/**
 * A task as a side sheet: properties (status, priority, due date, reminder,
 * repeat, assignee, project, GitHub), and its thread with the agent working on it. `refreshTick` changes
 * whenever the backend broadcasts an event, so agent replies appear live.
 */
export function TaskDialog({ taskId, agents, projects, refreshTick, onClose, onChanged }: {
  taskId: string | null;
  agents: api.Agent[];
  projects: api.Project[];
  refreshTick: number;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [task, setTask] = useState<api.TaskDetail | null>(null);
  const [reply, setReply] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    if (!taskId) return;
    try {
      setTask(await api.tasks.get(taskId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load task');
    }
  }, [taskId]);

  useEffect(() => {
    setTask(null);
    setReply('');
    setError(null);
    load();
  }, [taskId, load]);

  useEffect(() => { load(); }, [refreshTick, load]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ block: 'end' });
  }, [task?.comments.length, task?.agent_running]);

  /** Run a change, then reload the task. Returns false (and shows the error) on failure. */
  const run = async (fn: () => Promise<unknown>, failure: string): Promise<boolean> => {
    if (!task) return false;
    setError(null);
    try {
      await fn();
      await load();
      onChanged();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : failure);
      return false;
    }
  };

  const handleSend = async () => {
    if (!task || !reply.trim()) return;
    setSending(true);
    if (await run(() => api.tasks.comment(task.id, reply.trim()), 'Could not send')) setReply('');
    setSending(false);
  };

  const handleDelete = async () => {
    if (!task || !confirm(`Delete “${task.text}”?`)) return;
    await api.tasks.delete(task.id);
    onChanged();
    onClose();
  };

  const assignable = agents.filter((a) => a.status !== 'disabled');
  const assignee = task?.assigned_agent_name ? agentDisplay(task.assigned_agent_name) : null;
  const project = projects.find((p) => p.id === task?.project_id);

  return (
    <Dialog.Root open={!!taskId} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/30 z-40" />
        <Dialog.Content
          aria-describedby={undefined}
          onOpenAutoFocus={(e) => e.preventDefault()}
          className="fixed right-0 top-0 h-full w-full max-w-2xl bg-mc-panel border-l border-mc-line shadow-sheet z-50 flex flex-col animate-sheet-in outline-none"
        >
          {/* Top bar */}
          <div className="flex items-center gap-2 h-12 px-4 border-b border-mc-line flex-shrink-0">
            <span className="flex items-center gap-1.5 text-xs text-mc-muted min-w-0">
              {project ? (
                <>
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: project.color || '#a1a1aa' }} />
                  <span className="truncate">{project.name}</span>
                </>
              ) : 'No project'}
              <span className="text-mc-dim">/</span>
              <span className="text-mc-dim">Task</span>
            </span>
            <span className="flex-1" />
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <button aria-label="More" className="w-7 h-7 rounded-md flex items-center justify-center text-mc-muted hover:text-mc-text hover:bg-mc-hover cursor-pointer">
                  <MoreHorizontal size={16} />
                </button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content align="end" sideOffset={4} className={menuContent}>
                  <DropdownMenu.Item onSelect={handleDelete} className={clsx(menuItem, 'text-red-600 dark:text-red-400')}>
                    <Trash2 size={14} /> Delete task
                  </DropdownMenu.Item>
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
            <Dialog.Close aria-label="Close" className="w-7 h-7 rounded-md flex items-center justify-center text-mc-muted hover:text-mc-text hover:bg-mc-hover cursor-pointer">
              <X size={16} />
            </Dialog.Close>
          </div>

          {!task ? (
            <div className="flex-1 flex items-center justify-center">
              <Dialog.Title className="sr-only">Task</Dialog.Title>
              {error ? <p className="text-sm text-red-600">{error}</p> : <Spinner />}
            </div>
          ) : (
            <>
              <div className="flex-1 overflow-y-auto">
                {/* Title + properties */}
                <div className="px-6 pt-5 pb-4 border-b border-mc-line">
                  <Dialog.Title className="text-lg font-semibold text-mc-text leading-snug break-words">{task.text}</Dialog.Title>
                  {task.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {task.tags.map((t) => <Badge key={t} variant={t === 'lead' ? 'purple' : 'default'}>{t}</Badge>)}
                    </div>
                  )}

                  <div className="mt-4 grid gap-0.5">
                    <Property label="Status">
                      <DropdownMenu.Root>
                        <PropertyTrigger>
                          <TaskStatusIcon status={task.status} size={14} />
                          <span>{taskStatusLabel(task.status)}</span>
                        </PropertyTrigger>
                        <DropdownMenu.Portal>
                          <DropdownMenu.Content align="start" sideOffset={4} className={menuContent}>
                            {STATUSES.map((s) => (
                              <DropdownMenu.Item key={s} className={menuItem} onSelect={() => run(() => api.tasks.update(task.id, { status: s }), 'Could not update')}>
                                <TaskStatusIcon status={s} size={14} /> {taskStatusLabel(s)}
                                {s === task.status && <Check size={13} className="ml-auto text-mc-muted" />}
                              </DropdownMenu.Item>
                            ))}
                          </DropdownMenu.Content>
                        </DropdownMenu.Portal>
                      </DropdownMenu.Root>
                    </Property>

                    <Property label="Priority">
                      <DropdownMenu.Root>
                        <PropertyTrigger>
                          <PriorityIcon priority={task.priority} />
                          <span className="capitalize">{task.priority}</span>
                        </PropertyTrigger>
                        <DropdownMenu.Portal>
                          <DropdownMenu.Content align="start" sideOffset={4} className={menuContent}>
                            {PRIORITIES.map((p) => (
                              <DropdownMenu.Item key={p} className={menuItem} onSelect={() => run(() => api.tasks.update(task.id, { priority: p }), 'Could not update')}>
                                <PriorityIcon priority={p} /> <span className="capitalize">{p}</span>
                                {p === task.priority && <Check size={13} className="ml-auto text-mc-muted" />}
                              </DropdownMenu.Item>
                            ))}
                          </DropdownMenu.Content>
                        </DropdownMenu.Portal>
                      </DropdownMenu.Root>
                    </Property>

                    <Property label="Due">
                      <DuePicker value={task.due_date} done={task.status === 'done'}
                        onChange={(due_date) => run(() => api.tasks.update(task.id, { due_date }), 'Could not set the due date')} />
                    </Property>

                    <Property label="Reminder">
                      <ReminderPicker value={task.remind_at} sent={!!task.remind_at && !reminderPending(task)}
                        onChange={(remind_at) => run(() => api.tasks.update(task.id, { remind_at }), 'Could not set the reminder')} />
                    </Property>

                    <Property label="Repeat">
                      <DropdownMenu.Root>
                        <PropertyTrigger>
                          <Repeat size={13} className="text-mc-muted" />
                          {task.recurrence ? <span>{REPEAT_LABELS[task.recurrence]}</span> : <span className="text-mc-muted">Never</span>}
                        </PropertyTrigger>
                        <DropdownMenu.Portal>
                          <DropdownMenu.Content align="start" sideOffset={4} className={menuContent}>
                            {([null, ...RECURRENCES] as (api.Recurrence | null)[]).map((r) => (
                              <DropdownMenu.Item key={r ?? 'never'} className={menuItem} onSelect={() => run(() => api.tasks.update(task.id, { recurrence: r }), 'Could not update')}>
                                {r ? REPEAT_LABELS[r] : 'Never'}
                                {r === (task.recurrence ?? null) && <Check size={13} className="ml-auto text-mc-muted" />}
                              </DropdownMenu.Item>
                            ))}
                            <p className="px-2 pt-1 pb-1.5 text-2xs text-mc-dim max-w-[220px]">Completing it creates the next one.</p>
                          </DropdownMenu.Content>
                        </DropdownMenu.Portal>
                      </DropdownMenu.Root>
                    </Property>

                    {!task.github_issue && (
                      <Property label="Assignee">
                        <DropdownMenu.Root>
                          <PropertyTrigger>
                            {assignee ? (
                              <>
                                <Avatar name={task.assigned_agent_name!} size={18} />
                                <span className="truncate">{task.assigned_agent_name}</span>
                                {task.agent_running && <Spinner size={12} />}
                              </>
                            ) : <span className="text-mc-muted">Assign an agent</span>}
                          </PropertyTrigger>
                          <DropdownMenu.Portal>
                            <DropdownMenu.Content align="start" sideOffset={4} className={clsx(menuContent, 'w-72')}>
                              {assignable.map((a) => {
                                const d = agentDisplay(a.name);
                                return (
                                  <DropdownMenu.Item key={a.id} className={clsx(menuItem, 'h-auto py-1.5 items-start')} onSelect={() => run(() => api.tasks.assign(task.id, a.id), 'Could not assign')}>
                                    <Avatar name={a.name} size={20} className="mt-0.5" />
                                    <span className="min-w-0 flex-1">
                                      <span className="block text-mc-text">{d.name} <span className="text-mc-dim">· {d.role}</span></span>
                                      <span className="block text-2xs text-mc-dim truncate">{a.description}</span>
                                    </span>
                                    {a.id === task.assigned_agent_id && <Check size={13} className="text-mc-muted mt-1" />}
                                  </DropdownMenu.Item>
                                );
                              })}
                              {task.assigned_agent_id && (
                                <>
                                  <DropdownMenu.Separator className="h-px bg-mc-line my-1" />
                                  <DropdownMenu.Item className={menuItem} onSelect={() => run(() => api.tasks.assign(task.id, null), 'Could not unassign')}>
                                    Unassign
                                  </DropdownMenu.Item>
                                </>
                              )}
                            </DropdownMenu.Content>
                          </DropdownMenu.Portal>
                        </DropdownMenu.Root>
                      </Property>
                    )}

                    <Property label="Project">
                      <DropdownMenu.Root>
                        <PropertyTrigger>
                          {project ? (
                            <>
                              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: project.color || '#a1a1aa' }} />
                              <span className="truncate">{project.name}</span>
                            </>
                          ) : <span className="text-mc-muted flex items-center gap-1.5"><FolderOpen size={13} /> No project</span>}
                        </PropertyTrigger>
                        <DropdownMenu.Portal>
                          <DropdownMenu.Content align="start" sideOffset={4} className={menuContent}>
                            {projects.map((p) => (
                              <DropdownMenu.Item key={p.id} className={menuItem} onSelect={() => run(() => api.tasks.update(task.id, { project_id: p.id }), 'Could not change project')}>
                                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color || '#a1a1aa' }} /> {p.name}
                                {p.id === task.project_id && <Check size={13} className="ml-auto text-mc-muted" />}
                              </DropdownMenu.Item>
                            ))}
                            {task.project_id && (
                              <DropdownMenu.Item className={menuItem} onSelect={() => run(() => api.tasks.update(task.id, { project_id: null }), 'Could not change project')}>
                                No project
                              </DropdownMenu.Item>
                            )}
                          </DropdownMenu.Content>
                        </DropdownMenu.Portal>
                      </DropdownMenu.Root>
                    </Property>

                    {(task.github_issue || task.project_has_repo) && (
                      <Property label="Code">
                        {task.github_issue ? (
                          <a href={task.github_issue} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm text-mc-accent hover:underline">
                            <GitPullRequest size={14} /> GitHub issue <ExternalLink size={11} />
                          </a>
                        ) : (
                          <Button size="sm" icon={GitPullRequest} loading={sending} onClick={() => run(() => api.tasks.sendToGitHub(task.id), 'Could not open the GitHub issue')}>
                            Send to Claude Code
                          </Button>
                        )}
                      </Property>
                    )}

                    {task.url && !task.github_issue && (
                      <Property label="Link">
                        <a href={task.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm text-mc-accent hover:underline max-w-full">
                          <Link2 size={13} className="flex-shrink-0" /> <span className="truncate">{task.url.replace(/^https?:\/\//, '')}</span>
                        </a>
                      </Property>
                    )}
                  </div>

                  {task.description && (
                    <Markdown className="mt-4 text-sm text-mc-secondary">{task.description}</Markdown>
                  )}
                </div>

                {/* Thread */}
                <div className="px-6 py-5">
                  <div className="text-xs font-medium text-mc-muted mb-4">Activity</div>
                  {task.comments.length === 0 && !task.agent_running && (
                    <p className="text-sm text-mc-dim">
                      No activity yet. Assign an agent to hand this off{task.project_has_repo ? ', or send it to Claude Code' : ''}.
                    </p>
                  )}
                  <ol className="relative flex flex-col gap-5">
                    {task.comments.length > 1 && <span aria-hidden className="absolute left-[11px] top-3 bottom-3 w-px bg-mc-line" />}
                    {task.comments.map((c) => {
                      const name = authorName(c.author, agents);
                      if (c.author === 'system') {
                        return (
                          <li key={c.id} className="relative flex items-start gap-3 text-xs text-mc-muted">
                            <span className="w-6 flex justify-center pt-1"><span className="w-2 h-2 rounded-full bg-mc-line-strong ring-4 ring-mc-panel" /></span>
                            <span className="flex-1 pt-0.5"><Markdown>{c.body}</Markdown></span>
                            <span className="text-mc-dim pt-0.5 flex-shrink-0">{timeAgo(c.created_at)}</span>
                          </li>
                        );
                      }
                      return (
                        <li key={c.id} className="relative flex items-start gap-3">
                          <Avatar name={name} size={24} className="ring-4 ring-mc-panel" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-baseline gap-2 mb-0.5">
                              <span className="text-sm font-medium text-mc-text">{agentDisplay(name).name}</span>
                              <span className="text-2xs text-mc-dim">{timeAgo(c.created_at)}</span>
                            </div>
                            <Markdown className="text-sm text-mc-secondary">{c.body}</Markdown>
                          </div>
                        </li>
                      );
                    })}
                    {task.agent_running && (
                      <li className="relative flex items-center gap-3">
                        <Avatar name={task.assigned_agent_name || 'Agent'} size={24} className="ring-4 ring-mc-panel" />
                        <span className="text-sm text-shimmer">{assignee?.name ?? 'Agent'} is working on it…</span>
                      </li>
                    )}
                  </ol>
                  <div ref={bottomRef} />
                </div>
              </div>

              {/* Composer */}
              <div className="flex-shrink-0 border-t border-mc-line p-4">
                {error && <p className="text-xs text-red-600 dark:text-red-400 mb-2">{error}</p>}
                <div className="relative">
                  <textarea
                    value={reply}
                    onChange={(e) => setReply(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSend(); }}
                    rows={3}
                    placeholder={
                      task.assigned_agent_name ? `Reply to ${task.assigned_agent_name}…`
                        : task.github_issue ? 'Comment on the GitHub issue…' : 'Add a note…'
                    }
                    className={clsx(textareaClass, 'pr-12')}
                  />
                  <button
                    onClick={handleSend}
                    disabled={sending || !reply.trim()}
                    aria-label="Send"
                    className="absolute right-2 bottom-2 w-8 h-8 flex items-center justify-center rounded-lg bg-mc-accent text-mc-accent-fg hover:bg-mc-accent-hover disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                  >
                    {sending ? <Spinner size={14} /> : <ArrowUp size={15} />}
                  </button>
                </div>
                <p className="mt-1.5 text-2xs text-mc-dim">
                  {task.assigned_agent_name ? `${assignee?.name} picks up your reply automatically.` : 'Notes stay on this task.'} ⌘↵ to send
                </p>
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
