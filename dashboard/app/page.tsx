'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { clsx } from 'clsx';
import {
  ArrowRight, Bot, CheckCheck, Check, CircleCheck, Inbox, Megaphone, MessageSquare, Play, Plus, Send, X,
} from 'lucide-react';
import * as api from './lib/api';
import { useWorkspace } from './components/workspace';
import {
  Avatar, Badge, Button, Card, EmptyState, IconButton, InlineInput, PriorityIcon, SectionHeader, Spinner,
  StatusIndicator, TaskStatusIcon, agentDisplay, timeAgo,
} from './components/shared';
import { DueBadge, dueInfo } from './components/schedule';
import { useLatestSteps } from './lib/live';
import { DraftDialog } from './components/draft-dialog';

const PRIORITY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
}

function Kpi({ label, value, tone, icon: Icon }: {
  label: string; value: number; tone?: 'rose' | 'emerald' | 'accent'; icon: React.ElementType;
}) {
  return (
    <Card className="px-4 py-3.5">
      <div className="flex items-center justify-between">
        <span className="text-xs text-mc-muted">{label}</span>
        <Icon size={14} className="text-mc-dim" />
      </div>
      <div className={clsx(
        'mt-1 text-2xl font-semibold tabular-nums tracking-tight',
        value > 0 && tone === 'rose' && 'text-rose-600 dark:text-rose-400',
        value > 0 && tone === 'emerald' && 'text-emerald-600 dark:text-emerald-400',
        value > 0 && tone === 'accent' && 'text-mc-accent',
        (!tone || value === 0) && 'text-mc-text',
      )}>
        {value}
      </div>
    </Card>
  );
}

function Row({ children, onClick, className }: { children: React.ReactNode; onClick?: () => void; className?: string }) {
  return (
    <div
      onClick={onClick}
      className={clsx('flex items-start gap-3 px-4 py-3 transition-colors', onClick && 'cursor-pointer hover:bg-mc-hover/50', className)}
    >
      {children}
    </div>
  );
}

// ─── Needs you ───────────────────────────────────────────

function NeedsYou() {
  const { approvals, tasks, content, agents, health, refresh, openTask } = useWorkspace();
  const [busy, setBusy] = useState<string | null>(null);
  const [openDraftId, setOpenDraftId] = useState<string | null>(null);

  const waiting = tasks.filter((t) => t.status === 'blocked');
  // Drafts to review, and approved ones still waiting to be posted
  const drafts = content.filter((c) => c.status === 'draft' || c.status === 'approved');
  const total = approvals.length + waiting.length + drafts.length;

  const act = async (id: string, fn: () => Promise<unknown>) => {
    setBusy(id);
    try { await fn(); await refresh(); } finally { setBusy(null); }
  };

  return (
    <section>
      <SectionHeader icon={Inbox} title="Needs you" count={total} />
      <Card className="divide-y divide-mc-line overflow-hidden">
        {total === 0 && (
          <EmptyState icon={CheckCheck} message="You're all caught up." small />
        )}

        {approvals.map((a) => {
          const agent = agents.find((x) => x.id === a.agent_id);
          return (
            <Row key={a.id} className="flex-wrap sm:flex-nowrap">
              <Avatar name={a.agent_name} size={24} />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-mc-text">
                  <span className="font-medium">{agentDisplay(agent?.name ?? a.agent_name).name}</span>
                  <span className="text-mc-muted"> wants to take {a.action_count} action{a.action_count === 1 ? '' : 's'}</span>
                </p>
                {a.summary && <p className="text-xs text-mc-muted mt-0.5 line-clamp-2">{a.summary}</p>}
                <div className="flex flex-wrap gap-1 mt-2">
                  {a.actions.slice(0, 4).map((act, i) => (
                    <Badge key={i}>{String(act.type).replace('create_', '+ ').replace('_', ' ')}: {String(act.text || act.title || act.key || '').slice(0, 48)}</Badge>
                  ))}
                </div>
              </div>
              <div className="flex gap-1.5 flex-shrink-0 w-full sm:w-auto pl-9 sm:pl-0">
                <Button size="sm" variant="success" icon={Check} loading={busy === a.id}
                  onClick={() => act(a.id, () => api.approvals.approve(a.id))}>Approve</Button>
                <Button size="sm" disabled={busy === a.id}
                  onClick={() => act(a.id, () => api.approvals.reject(a.id))}>Reject</Button>
              </div>
            </Row>
          );
        })}

        {waiting.map((t) => (
          <Row key={t.id} onClick={() => openTask(t.id)}>
            {t.assigned_agent_name ? <Avatar name={t.assigned_agent_name} size={24} /> : <TaskStatusIcon status={t.status} size={18} />}
            <div className="flex-1 min-w-0">
              <p className="text-sm text-mc-text truncate">{t.text}</p>
              <p className="text-xs text-mc-muted mt-0.5">
                {t.assigned_agent_name ? `${agentDisplay(t.assigned_agent_name).name} is waiting for your answer` : 'Blocked'}
              </p>
            </div>
            <Button size="sm" icon={MessageSquare}>Reply</Button>
          </Row>
        ))}

        {drafts.slice(0, 5).map((d) => (
          <Row key={d.id} onClick={() => setOpenDraftId(d.id)}>
            <span className="w-6 h-6 rounded-md bg-violet-500/10 text-violet-600 dark:text-violet-300 flex items-center justify-center flex-shrink-0">
              <Megaphone size={13} />
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-mc-text truncate">
                <span className="text-mc-muted">{d.status === 'approved' ? `Ready to post on ${d.channel}` : `Draft for ${d.channel}`} · </span>{d.title}
              </p>
              <p className="text-xs text-mc-muted mt-0.5 line-clamp-2">{d.body}</p>
            </div>
            <div className="flex gap-0.5 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
              {d.status === 'draft' && (
                <IconButton label="Approve draft" icon={Check} disabled={busy === d.id}
                  onClick={() => act(d.id, () => api.marketingContent.update(d.id, { status: 'approved' }))} />
              )}
              <IconButton label="Mark as posted" icon={Send} disabled={busy === d.id}
                onClick={() => act(d.id, () => api.marketingContent.update(d.id, { status: 'posted' }))} />
              <IconButton label="Discard draft" icon={X} disabled={busy === d.id}
                onClick={() => act(d.id, () => api.marketingContent.update(d.id, { status: 'archived' }))} />
            </div>
          </Row>
        ))}
      </Card>
      <DraftDialog
        draft={content.find((c) => c.id === openDraftId) ?? null}
        publishing={health?.publishing}
        onClose={() => setOpenDraftId(null)}
        onChanged={refresh}
      />
    </section>
  );
}

// ─── Delegated work ──────────────────────────────────────

function WithAgents() {
  const { tasks, agents, projects, openTask, openCommandMenu } = useWorkspace();
  const delegated = tasks.filter((t) => t.assigned_agent_id && (t.status === 'todo' || t.status === 'in_progress'));
  const steps = useLatestSteps();

  return (
    <section>
      <SectionHeader icon={Bot} title="With agents" count={delegated.length} />
      <Card className="divide-y divide-mc-line overflow-hidden">
        {delegated.length === 0 && (
          <EmptyState icon={Bot} message="Nothing delegated right now." small>
            <button onClick={openCommandMenu} className="mt-2 text-xs text-mc-accent hover:underline cursor-pointer">
              Press ⌘K, describe a task, and hand it to an agent
            </button>
          </EmptyState>
        )}
        {delegated.map((t) => {
          const agent = agents.find((a) => a.id === t.assigned_agent_id);
          const working = agent?.status === 'running';
          const project = projects.find((p) => p.id === t.project_id);
          return (
            <Row key={t.id} onClick={() => openTask(t.id)} className="items-center">
              <Avatar name={t.assigned_agent_name ?? 'Agent'} size={24} />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-mc-text truncate">{t.text}</p>
                <p className="text-xs mt-0.5 flex items-center gap-1.5">
                  {working
                    ? <span className="text-shimmer truncate">{agentDisplay(t.assigned_agent_name).name}{steps[t.id] ? `: ${steps[t.id]}` : ' is working…'}</span>
                    : <span className="text-mc-muted">{agentDisplay(t.assigned_agent_name).name} · in progress</span>}
                  {project && (
                    <span className="flex items-center gap-1 text-mc-dim">
                      · <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: project.color }} />{project.name}
                    </span>
                  )}
                </p>
              </div>
              <ArrowRight size={14} className="text-mc-dim" />
            </Row>
          );
        })}
      </Card>
    </section>
  );
}

// ─── Your tasks ──────────────────────────────────────────

/** Overdue first, then due today, then everything else. */
function urgency(t: api.Task): number {
  if (!t.due_date) return 2;
  const tone = dueInfo(t.due_date).tone;
  return tone === 'overdue' ? 0 : tone === 'today' ? 1 : 2;
}

function YourTasks() {
  const { tasks, projects, refresh, openTask } = useWorkspace();
  const [adding, setAdding] = useState(false);

  const mine = tasks
    .filter((t) => !t.assigned_agent_id && (t.status === 'todo' || t.status === 'in_progress') && !t.tags.includes('lead'))
    .sort((a, b) => urgency(a) - urgency(b) || (PRIORITY_ORDER[a.priority] ?? 9) - (PRIORITY_ORDER[b.priority] ?? 9));

  const complete = async (id: string) => {
    await api.tasks.update(id, { status: 'done' });
    refresh();
  };

  return (
    <section>
      <SectionHeader
        icon={CircleCheck}
        title="Your tasks"
        count={mine.length}
        onAdd={() => setAdding(true)}
        extra={<Link href="/tasks" className="text-xs text-mc-muted hover:text-mc-text px-1.5">View board</Link>}
      />
      {adding && (
        <InlineInput placeholder="What needs doing?" onCancel={() => setAdding(false)}
          onSubmit={async (text) => { await api.tasks.create({ text }); setAdding(false); refresh(); }} />
      )}
      <Card className="divide-y divide-mc-line overflow-hidden">
        {mine.length === 0 && <EmptyState icon={CircleCheck} message="No open tasks of your own." small />}
        {mine.slice(0, 8).map((t) => {
          const project = projects.find((p) => p.id === t.project_id);
          return (
            <div key={t.id} className="group flex items-center gap-3 px-4 h-11 hover:bg-mc-hover/50 transition-colors">
              <button
                onClick={() => complete(t.id)}
                aria-label="Mark done"
                className="w-4 h-4 rounded-full ring-1 ring-mc-line-strong hover:ring-mc-accent hover:bg-mc-accent/10 flex items-center justify-center cursor-pointer flex-shrink-0"
              >
                <Check size={10} className="text-transparent group-hover:text-mc-accent" />
              </button>
              <PriorityIcon priority={t.priority} />
              <button onClick={() => openTask(t.id)} className="flex-1 min-w-0 text-left text-sm text-mc-text truncate cursor-pointer">
                {t.text}
              </button>
              {project && (
                <span className="hidden sm:flex items-center gap-1.5 text-xs text-mc-muted flex-shrink-0">
                  <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: project.color }} />{project.name}
                </span>
              )}
              <DueBadge task={t} className="flex-shrink-0" />
            </div>
          );
        })}
        {mine.length > 8 && (
          <Link href="/tasks" className="flex items-center justify-center h-9 text-xs text-mc-muted hover:text-mc-text">
            {mine.length - 8} more on the board
          </Link>
        )}
      </Card>
    </section>
  );
}

// ─── Activity ────────────────────────────────────────────

function Activity() {
  const { tick, openTask } = useWorkspace();
  const [items, setItems] = useState<api.ActivityItem[] | null>(null);

  useEffect(() => {
    api.activity.list(15).then(setItems).catch(() => setItems([]));
  }, [tick]);

  return (
    <section>
      <SectionHeader icon={MessageSquare} title="Activity" />
      <Card className="p-1.5">
        {items === null && <div className="py-8 flex justify-center"><Spinner /></div>}
        {items?.length === 0 && <EmptyState icon={MessageSquare} message="Agent replies show up here." small />}
        {items?.map((e) => (
          <button
            key={e.id}
            onClick={() => openTask(e.task.id)}
            className="w-full flex items-start gap-2.5 px-2.5 py-2 rounded-lg text-left hover:bg-mc-hover/60 cursor-pointer"
          >
            <Avatar name={e.author_name} size={20} className="mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-xs text-mc-muted truncate">
                <span className="font-medium text-mc-text">{agentDisplay(e.author_name).name}</span>
                {e.author === 'system' ? ' · ' : ' on '}
                <span className="text-mc-secondary">{e.task.text}</span>
              </p>
              <p className="text-xs text-mc-muted line-clamp-2 mt-0.5">{e.body.replace(/[#*_`>|-]+/g, ' ').replace(/\s+/g, ' ').trim()}</p>
            </div>
            <span className="text-2xs text-mc-dim flex-shrink-0 mt-0.5">{timeAgo(e.created_at)}</span>
          </button>
        ))}
      </Card>
    </section>
  );
}

// ─── Agents ──────────────────────────────────────────────

function AgentsGlance() {
  const { agents, refresh } = useWorkspace();
  const visible = agents.filter((a) => a.status !== 'disabled');

  const runNow = async (id: string) => {
    try { await api.agents.run(id); } finally { refresh(); }
  };

  return (
    <section>
      <SectionHeader icon={Bot} title="Agents" extra={<Link href="/agents" className="text-xs text-mc-muted hover:text-mc-text px-1.5">Manage</Link>} />
      <Card className="p-1.5">
        {visible.map((a) => {
          const d = agentDisplay(a.name);
          return (
            <div key={a.id} className="group flex items-center gap-2.5 px-2.5 h-10 rounded-lg hover:bg-mc-hover/60">
              <Avatar name={a.name} size={22} />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-mc-text truncate leading-tight">{d.name} <span className="text-mc-dim">{d.role}</span></p>
              </div>
              {a.status === 'running'
                ? <span className="flex items-center gap-1.5 text-2xs text-emerald-600 dark:text-emerald-400"><StatusIndicator status="running" /> running</span>
                : (
                  <>
                    <span className={clsx('text-2xs group-hover:hidden', a.status === 'error' ? 'text-red-500' : 'text-mc-dim')}>
                      {a.status === 'error' ? 'last run failed' : a.last_run_at ? timeAgo(a.last_run_at) : 'never run'}
                    </span>
                    <IconButton label={`Run ${d.name}`} icon={Play} className="hidden group-hover:inline-flex" onClick={() => runNow(a.id)} />
                  </>
                )}
            </div>
          );
        })}
      </Card>
    </section>
  );
}

// ─── Page ────────────────────────────────────────────────

export default function HomePage() {
  const { loaded, tasks, agents, approvals, content, openCommandMenu } = useWorkspace();
  const today = useMemo(() => new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' }), []);

  const waiting = tasks.filter((t) => t.status === 'blocked').length + approvals.length;
  const working = agents.filter((a) => a.status === 'running').length;
  const open = tasks.filter((t) => t.status !== 'done').length;
  const drafts = content.filter((c) => c.status === 'draft').length;

  return (
    <>
      <div className="max-w-[1400px] mx-auto px-4 sm:px-8 pt-8 pb-2 flex items-end justify-between gap-4">
        <div>
          <p className="text-xs text-mc-muted">{today}</p>
          <h1 className="text-2xl font-semibold tracking-tight text-mc-text mt-0.5">{greeting()}</h1>
        </div>
        <Button variant="primary" icon={Plus} onClick={openCommandMenu}>New task</Button>
      </div>

      {!loaded ? (
        <div className="py-24 flex justify-center"><Spinner size={20} /></div>
      ) : (
        <main className="max-w-[1400px] mx-auto px-4 sm:px-8 py-6 space-y-8 animate-fade-up">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Kpi label="Waiting on you" value={waiting} tone="rose" icon={Inbox} />
            <Kpi label="Agents working" value={working} tone="emerald" icon={Bot} />
            <Kpi label="Open tasks" value={open} icon={CircleCheck} />
            <Kpi label="Drafts to review" value={drafts} tone="accent" icon={Megaphone} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-8">
              <NeedsYou />
              <WithAgents />
              <YourTasks />
            </div>
            <div className="space-y-8">
              <Activity />
              <AgentsGlance />
            </div>
          </div>
        </main>
      )}
    </>
  );
}
