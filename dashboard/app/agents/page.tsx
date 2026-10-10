'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import * as Tooltip from '@radix-ui/react-tooltip';
import { clsx } from 'clsx';
import { Bot, CheckCircle, ChevronRight, Pencil, Play, Plus, Square, XCircle } from 'lucide-react';
import * as api from '../lib/api';
import { useWorkspace } from '../components/workspace';
import { Markdown } from '../components/markdown';
import {
  Avatar, Badge, Button, Card, EmptyState, PageHeader, Spinner, StatusIndicator, agentDisplay, timeAgo,
} from '../components/shared';

interface RunDetail {
  id: string;
  status: string;
  trigger: string;
  tokens_used: number;
  cost_usd: number;
  error: string | null;
  output_data: Record<string, unknown> | null;
  started_at: string;
  completed_at: string | null;
  transcript: { role: string; content: string }[] | null;
}

function scheduleLabel(a: api.Agent): string {
  if (!a.schedule_type || a.schedule_type === 'manual') return 'On demand';
  if (a.schedule_type === 'interval') return `Every ${a.schedule_value}`;
  return `Cron ${a.schedule_value}`;
}

function Toast({ message, type, onDone }: { message: string; type: 'success' | 'error'; onDone: () => void }) {
  useEffect(() => { const t = setTimeout(onDone, 3000); return () => clearTimeout(t); }, [onDone]);
  return (
    <div className="fixed bottom-4 right-4 z-50 flex items-center gap-2 px-3.5 h-10 rounded-lg bg-mc-text text-mc-panel text-sm shadow-dropdown animate-fade-up">
      {type === 'success' ? <CheckCircle size={15} className="text-emerald-400" /> : <XCircle size={15} className="text-red-400" />}
      {message}
    </div>
  );
}

function RunRow({ run, isExpanded, onToggle }: { run: RunDetail; isExpanded: boolean; onToggle: () => void }) {
  const out = (run.output_data ?? {}) as Record<string, unknown>;
  const summary = (out.reply as string) || (out.summary as string) || null;
  const actions = (out.actions as unknown[]) || [];
  const duration = run.completed_at
    ? Math.round((new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000)
    : null;

  return (
    <div className="border-b border-mc-line last:border-0">
      <button onClick={onToggle} className="w-full flex items-center gap-3 h-10 px-4 text-left hover:bg-mc-hover/50 cursor-pointer">
        <ChevronRight size={13} className={clsx('text-mc-dim transition-transform', isExpanded && 'rotate-90')} />
        <span className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0',
          run.status === 'completed' ? 'bg-emerald-500' : run.status === 'failed' ? 'bg-red-500'
            : run.status === 'running' ? 'bg-amber-400 animate-pulse' : 'bg-mc-line-strong')} />
        <span className="text-sm text-mc-text w-36 flex-shrink-0">
          {new Date(run.started_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
        </span>
        <span className="text-xs text-mc-muted flex-1 truncate">{run.trigger}</span>
        <span className="text-xs text-mc-dim tabular-nums w-12 text-right">{duration !== null ? `${duration}s` : '—'}</span>
        <span className="text-xs text-mc-muted font-mono tabular-nums w-16 text-right">${run.cost_usd.toFixed(3)}</span>
      </button>
      {isExpanded && (
        <div className="px-11 pb-4 space-y-3">
          {run.error && <div className="text-xs text-red-600 dark:text-red-400 bg-red-500/5 ring-1 ring-red-500/20 rounded-lg px-3 py-2">{run.error}</div>}
          {summary && <Markdown className="text-sm text-mc-secondary">{summary}</Markdown>}
          <div className="text-2xs text-mc-dim">
            {actions.length} action{actions.length === 1 ? '' : 's'}
            {run.tokens_used > 0 && ` · ${run.tokens_used.toLocaleString()} tokens`}
          </div>
          {run.transcript && run.transcript.length > 0 && (
            <details>
              <summary className="text-xs text-mc-accent cursor-pointer hover:underline">Transcript ({run.transcript.length} messages)</summary>
              <div className="mt-2 space-y-1.5 max-h-72 overflow-y-auto">
                {run.transcript.map((msg, i) => (
                  <div key={i} className="text-xs px-3 py-2 rounded-lg bg-mc-subtle ring-1 ring-mc-line">
                    <span className="font-medium text-2xs uppercase text-mc-dim mr-1.5">{msg.role}</span>
                    <span className="whitespace-pre-wrap text-mc-secondary">{msg.content}</span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: React.ReactNode; tone?: 'good' | 'warn' }) {
  return (
    <div>
      <div className="text-2xs text-mc-muted uppercase tracking-wider">{label}</div>
      <div className={clsx('text-sm font-medium mt-0.5 tabular-nums',
        tone === 'good' ? 'text-emerald-600 dark:text-emerald-400' : tone === 'warn' ? 'text-amber-600 dark:text-amber-400' : 'text-mc-text')}>
        {value}
      </div>
    </div>
  );
}

export default function AgentsPage() {
  const { agents, loaded, refresh, tick } = useWorkspace();
  const [analytics, setAnalytics] = useState<api.AgentAnalytics | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [runs, setRuns] = useState<RunDetail[]>([]);
  const [expandedRun, setExpandedRun] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [starting, setStarting] = useState<string | null>(null);

  useEffect(() => { api.agents.analytics().then(setAnalytics).catch(() => {}); }, [tick]);

  useEffect(() => {
    if (!selectedId && agents.length) setSelectedId((agents.find((a) => a.status !== 'disabled') ?? agents[0]).id);
  }, [agents, selectedId]);

  const loadRuns = useCallback(() => {
    if (!selectedId) return;
    api.agents.runs(selectedId, 20).then((r) => setRuns(r as RunDetail[])).catch(() => {});
  }, [selectedId]);

  useEffect(() => { loadRuns(); }, [loadRuns, tick]);

  const selected = agents.find((a) => a.id === selectedId) ?? null;
  const stats = analytics?.agents.find((a) => a.agent_id === selectedId);
  const totals = analytics?.totals;
  const running = agents.filter((a) => a.status === 'running').length;

  const trigger = async (a: api.Agent) => {
    setStarting(a.id);
    try {
      await api.agents.run(a.id);
      setToast({ message: `${agentDisplay(a.name).name} started`, type: 'success' });
    } catch (err) {
      setToast({ message: err instanceof Error ? err.message : 'Could not start', type: 'error' });
    } finally {
      setStarting(null);
      refresh();
    }
  };

  const stop = async (a: api.Agent) => {
    await api.agents.stop(a.id).catch(() => {});
    refresh();
  };

  const expandRun = async (run: RunDetail) => {
    if (expandedRun === run.id) { setExpandedRun(null); return; }
    setExpandedRun(run.id);
    if (!run.transcript && selectedId) {
      try {
        const detail = await api.agents.runDetail(selectedId, run.id);
        setRuns((prev) => prev.map((r) => (r.id === run.id ? { ...r, transcript: detail.transcript } : r)));
      } catch {}
    }
  };

  const dailyCosts = stats ? Object.entries(stats.daily_costs).slice(-14) : [];
  const maxCost = Math.max(...dailyCosts.map(([, c]) => c), 0.01);

  return (
    <Tooltip.Provider delayDuration={150}>
      {toast && <Toast message={toast.message} type={toast.type} onDone={() => setToast(null)} />}
      <PageHeader
        title="Agents"
        subtitle={`${agents.length} agents · ${running} running${totals ? ` · $${totals.total_cost_usd.toFixed(2)} in the last ${analytics?.days} days` : ''}`}
        actions={<Link href="/agents/new"><Button variant="primary" icon={Plus}>New agent</Button></Link>}
      />

      {!loaded ? (
        <div className="py-24 flex justify-center"><Spinner size={20} /></div>
      ) : agents.length === 0 ? (
        <EmptyState icon={Bot} message="No agents yet. Add a YAML file to backend/skills/ or create one here." />
      ) : (
        <main className="max-w-[1400px] mx-auto px-4 sm:px-8 py-6 grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-6">
          {/* List */}
          <div className="flex flex-col gap-0.5">
            {agents.map((a) => {
              const d = agentDisplay(a.name);
              return (
                <button
                  key={a.id}
                  onClick={() => { setSelectedId(a.id); setExpandedRun(null); }}
                  className={clsx(
                    'flex items-center gap-3 px-3 h-14 rounded-lg text-left transition-colors cursor-pointer',
                    a.id === selectedId ? 'bg-mc-panel ring-1 ring-mc-line shadow-card' : 'hover:bg-mc-hover/60',
                    a.status === 'disabled' && 'opacity-50',
                  )}
                >
                  <Avatar name={a.name} size={30} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-mc-text truncate">{d.name}</p>
                    <p className="text-xs text-mc-muted truncate">{d.role || a.agent_type}</p>
                  </div>
                  <StatusIndicator status={a.status} />
                </button>
              );
            })}
          </div>

          {/* Detail */}
          {selected && (
            <div className="space-y-5 min-w-0 animate-fade-up" key={selected.id}>
              <Card className="p-5">
                <div className="flex items-start gap-4">
                  <Avatar name={selected.name} size={44} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h2 className="text-lg font-semibold text-mc-text">{agentDisplay(selected.name).name}</h2>
                      <span className="text-sm text-mc-muted">{agentDisplay(selected.name).role}</span>
                      <Badge variant={selected.status === 'running' ? 'success' : selected.status === 'error' ? 'error' : 'default'}>
                        {selected.status === 'error' ? 'last run failed' : selected.status}
                      </Badge>
                    </div>
                    <p className="text-sm text-mc-muted mt-1">{selected.description}</p>
                  </div>
                  <div className="flex gap-2 flex-shrink-0">
                    <Link href={`/agents/${selected.id}/edit`}><Button icon={Pencil}>Edit</Button></Link>
                    {selected.status === 'running'
                      ? <Button variant="danger" icon={Square} onClick={() => stop(selected)}>Stop</Button>
                      : <Button variant="primary" icon={Play} loading={starting === selected.id} disabled={selected.status === 'disabled'} onClick={() => trigger(selected)}>Run now</Button>}
                  </div>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 mt-5 pt-4 border-t border-mc-line">
                  <Stat label="Schedule" value={scheduleLabel(selected)} />
                  <Stat label="Model" value={<span className="font-mono text-xs">{selected.model.replace('claude-', '')}</span>} />
                  <Stat label="Last run" value={timeAgo(selected.last_run_at)} />
                  <Stat label={`Runs · ${analytics?.days ?? 30}d`} value={
                    stats ? <>{stats.total_runs} <span className={clsx('text-xs', stats.success_rate >= 80 ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600')}>({Math.round(stats.success_rate)}% ok)</span></> : '0'
                  } />
                  <Stat label={`Cost · ${analytics?.days ?? 30}d`} value={`$${(stats?.total_cost_usd ?? 0).toFixed(3)}`} />
                </div>
              </Card>

              {dailyCosts.length > 0 && (
                <Card className="p-5">
                  <div className="flex items-baseline justify-between mb-3">
                    <h3 className="text-sm font-medium text-mc-text">Daily cost</h3>
                    <span className="text-2xs text-mc-dim">as reported by the Agent SDK</span>
                  </div>
                  <div className="flex items-end gap-1.5 h-24">
                    {dailyCosts.map(([day, cost]) => (
                      <Tooltip.Root key={day}>
                        <Tooltip.Trigger asChild>
                          <div className="flex-1 max-w-10 rounded-t bg-mc-accent/70 hover:bg-mc-accent transition-colors" style={{ height: `${Math.max(4, (cost / maxCost) * 96)}px` }} />
                        </Tooltip.Trigger>
                        <Tooltip.Content className="bg-mc-text text-mc-panel text-xs px-2 py-1 rounded-md" sideOffset={4}>
                          {day} · ${cost.toFixed(4)}
                        </Tooltip.Content>
                      </Tooltip.Root>
                    ))}
                  </div>
                </Card>
              )}

              <Card className="overflow-hidden">
                <div className="flex items-center justify-between px-4 h-11 border-b border-mc-line">
                  <h3 className="text-sm font-medium text-mc-text">Recent runs</h3>
                  <span className="text-2xs text-mc-dim">click a run for its output and transcript</span>
                </div>
                {runs.slice(0, 15).map((r) => (
                  <RunRow key={r.id} run={r} isExpanded={expandedRun === r.id} onToggle={() => expandRun(r)} />
                ))}
                {runs.length === 0 && <EmptyState icon={Play} message="No runs yet" small />}
              </Card>
            </div>
          )}
        </main>
      )}
    </Tooltip.Provider>
  );
}
