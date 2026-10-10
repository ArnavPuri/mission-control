'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Bot, ChevronDown, ExternalLink, GitPullRequest, Loader2, Send, User, X } from 'lucide-react';
import { clsx } from 'clsx';
import * as api from '../lib/api';
import { Badge } from './shared';

const STATUS_VARIANT: Record<string, 'default' | 'warning' | 'success' | 'blue'> = {
  todo: 'default', in_progress: 'blue', blocked: 'warning', done: 'success',
};

const STATUS_LABEL: Record<string, string> = {
  todo: 'to do', in_progress: 'in progress', blocked: 'waiting on you', done: 'done',
};

function authorLabel(author: string, agents: api.Agent[]): string {
  if (author === 'user') return 'You';
  if (author === 'system') return 'System';
  const slug = author.replace(/^agent:/, '');
  return agents.find((a) => a.slug === slug)?.name ?? slug;
}

/**
 * A task with its thread: assign it to an agent, read what the agent said,
 * and reply. `refreshTick` changes whenever the backend broadcasts an event,
 * so agent replies show up without reopening the dialog.
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
  }, [task?.comments.length]);

  const assignable = agents.filter((a) => a.status !== 'disabled');

  const handleAssign = async (agentId: string | null) => {
    if (!task) return;
    setError(null);
    try {
      await api.tasks.assign(task.id, agentId);
      await load();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not assign');
    }
  };

  const handleProject = async (projectId: string) => {
    if (!task) return;
    setError(null);
    try {
      await api.tasks.update(task.id, { project_id: projectId || null });
      await load();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not change project');
    }
  };

  const handleGitHub = async () => {
    if (!task) return;
    setSending(true);
    setError(null);
    try {
      await api.tasks.sendToGitHub(task.id);
      await load();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not open the GitHub issue');
    } finally {
      setSending(false);
    }
  };

  const handleSend = async () => {
    if (!task || !reply.trim()) return;
    setSending(true);
    setError(null);
    try {
      await api.tasks.comment(task.id, reply.trim());
      setReply('');
      await load();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not send');
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog.Root open={!!taskId} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/30 z-40" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed right-0 top-0 h-full w-full max-w-xl bg-white dark:bg-gray-900 border-l border-mc-border dark:border-gray-800 shadow-dropdown z-50 flex flex-col"
        >
          {/* Header */}
          <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-mc-border dark:border-gray-800">
            <div className="min-w-0">
              <Dialog.Title className="text-base font-semibold text-mc-text dark:text-gray-100 break-words">
                {task?.text ?? 'Loading…'}
              </Dialog.Title>
              {task && (
                <div className="flex flex-wrap items-center gap-2 mt-2">
                  <Badge variant={STATUS_VARIANT[task.status]}>{STATUS_LABEL[task.status] ?? task.status}</Badge>
                  <Badge variant="default">{task.priority}</Badge>
                  {task.tags.map((t) => <Badge key={t} variant="purple">{t}</Badge>)}
                  {task.url && (
                    <a href={task.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-mc-accent hover:underline">
                      <ExternalLink size={11} /> link
                    </a>
                  )}
                </div>
              )}
            </div>
            <Dialog.Close className="text-mc-dim hover:text-mc-text dark:hover:text-gray-200 cursor-pointer" aria-label="Close">
              <X size={18} />
            </Dialog.Close>
          </div>

          {/* Project + GitHub */}
          {task && (
            <div className="flex flex-wrap items-center justify-between gap-2 px-5 py-3 border-b border-mc-border dark:border-gray-800 text-sm">
              <label className="flex items-center gap-2 text-mc-muted dark:text-gray-400">
                Project
                <select
                  value={task.project_id ?? ''}
                  onChange={(e) => handleProject(e.target.value)}
                  className="border border-mc-border dark:border-gray-700 rounded-lg px-2 py-1 text-sm bg-white dark:bg-gray-800 text-mc-text dark:text-gray-200"
                >
                  <option value="">None</option>
                  {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </label>
              {task.github_issue ? (
                <a href={task.github_issue} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-1.5 text-mc-accent hover:underline">
                  <GitPullRequest size={13} /> GitHub issue <ExternalLink size={11} />
                </a>
              ) : task.project_has_repo ? (
                <button onClick={handleGitHub} disabled={sending}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-mc-border dark:border-gray-700 text-mc-text dark:text-gray-200 hover:border-mc-accent/40 disabled:opacity-50 cursor-pointer">
                  <GitPullRequest size={13} /> Send to Claude Code
                </button>
              ) : null}
            </div>
          )}

          {/* Assignee */}
          {task && !task.github_issue && (
            <div className="flex items-center justify-between px-5 py-3 border-b border-mc-border dark:border-gray-800 text-sm">
              <span className="text-mc-muted dark:text-gray-400">Assigned to</span>
              <DropdownMenu.Root>
                <DropdownMenu.Trigger asChild>
                  <button className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-mc-border dark:border-gray-700 text-mc-text dark:text-gray-200 hover:border-mc-accent/40 cursor-pointer">
                    <Bot size={13} />
                    {task.assigned_agent_name ?? 'Nobody'}
                    {task.agent_running && <Loader2 size={12} className="animate-spin text-mc-accent" />}
                    <ChevronDown size={12} />
                  </button>
                </DropdownMenu.Trigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.Content align="end" sideOffset={4} className="bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-700 rounded-lg shadow-dropdown p-1 z-50 max-h-72 overflow-y-auto">
                    {assignable.map((a) => (
                      <DropdownMenu.Item
                        key={a.id}
                        onSelect={() => handleAssign(a.id)}
                        className="px-3 py-1.5 text-sm text-mc-text dark:text-gray-300 rounded cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 outline-none"
                      >
                        <div>{a.name}</div>
                        <div className="text-[11px] text-mc-dim max-w-[260px] truncate">{a.description}</div>
                      </DropdownMenu.Item>
                    ))}
                    {task.assigned_agent_id && (
                      <DropdownMenu.Item
                        onSelect={() => handleAssign(null)}
                        className="px-3 py-1.5 text-sm text-mc-muted rounded cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 outline-none border-t border-mc-border dark:border-gray-800 mt-1"
                      >
                        Unassign
                      </DropdownMenu.Item>
                    )}
                  </DropdownMenu.Content>
                </DropdownMenu.Portal>
              </DropdownMenu.Root>
            </div>
          )}

          {/* Thread */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
            {task?.description && (
              <p className="text-sm text-mc-muted dark:text-gray-400 whitespace-pre-wrap">{task.description}</p>
            )}
            {task && task.comments.length === 0 && (
              <p className="text-sm text-mc-dim dark:text-gray-500 text-center py-6">
                No conversation yet. Assign an agent to hand this off.
              </p>
            )}
            {task?.comments.map((c) => {
              const mine = c.author === 'user';
              const system = c.author === 'system';
              return (
                <div key={c.id} className={clsx('flex', mine ? 'justify-end' : 'justify-start')}>
                  <div
                    className={clsx(
                      'max-w-[85%] rounded-xl px-3 py-2 text-sm',
                      mine && 'bg-mc-accent text-white',
                      system && 'bg-amber-50 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
                      !mine && !system && 'bg-gray-100 text-mc-text dark:bg-gray-800 dark:text-gray-200',
                    )}
                  >
                    <div className={clsx('flex items-center gap-1 text-[11px] mb-1', mine ? 'text-white/80' : 'text-mc-dim dark:text-gray-500')}>
                      {mine ? <User size={10} /> : <Bot size={10} />}
                      {authorLabel(c.author, agents)} · {new Date(c.created_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                    </div>
                    <div className="whitespace-pre-wrap break-words">{c.body}</div>
                  </div>
                </div>
              );
            })}
            {task?.agent_running && (
              <div className="flex items-center gap-2 text-xs text-mc-dim dark:text-gray-500">
                <Loader2 size={12} className="animate-spin" /> {task.assigned_agent_name} is working on it…
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Reply */}
          {task && (
            <div className="border-t border-mc-border dark:border-gray-800 px-5 py-3">
              {error && <p className="text-xs text-red-600 dark:text-red-400 mb-2">{error}</p>}
              <div className="flex items-end gap-2">
                <textarea
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSend(); }}
                  rows={2}
                  placeholder={
                    task.assigned_agent_name ? `Reply to ${task.assigned_agent_name}…`
                      : task.github_issue ? 'Comment on the GitHub issue…' : 'Add a note…'
                  }
                  className="flex-1 resize-none border border-mc-border dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-mc-text dark:text-gray-200 bg-white dark:bg-gray-800 outline-none focus:border-mc-accent placeholder:text-mc-dim"
                />
                <button
                  onClick={handleSend}
                  disabled={sending || !reply.trim()}
                  aria-label="Send"
                  className="h-9 w-9 flex items-center justify-center rounded-lg bg-mc-accent text-white hover:bg-blue-700 disabled:opacity-50 cursor-pointer"
                >
                  {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                </button>
              </div>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
