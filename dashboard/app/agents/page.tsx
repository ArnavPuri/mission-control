'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import * as api from '../lib/api';
import * as Progress from '@radix-ui/react-progress';
import * as Tooltip from '@radix-ui/react-tooltip';
import {
  Zap, Play, Square, Clock, DollarSign, Activity,
  BarChart3, Loader2, TrendingUp, AlertTriangle, Plus, Pencil,
  ChevronDown, ChevronRight, CheckCircle, XCircle,
} from 'lucide-react';
import { clsx } from 'clsx';
import Link from 'next/link';
import { Card, Badge, StatusIndicator, EmptyState } from '../components/shared';

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

function Toast({ message, type, onDone }: { message: string; type: 'success' | 'error'; onDone: () => void }) {
  useEffect(() => { const t = setTimeout(onDone, 3000); return () => clearTimeout(t); }, [onDone]);
  return (
    <div className={clsx(
      'fixed top-4 right-4 z-50 px-4 py-2.5 rounded-lg shadow-lg text-sm font-medium flex items-center gap-2 animate-in slide-in-from-top-2',
      type === 'success' ? 'bg-mc-green text-white' : 'bg-mc-red text-white'
    )}>
      {type === 'success' ? <CheckCircle size={16} /> : <XCircle size={16} />}
      {message}
    </div>
  );
}

function RunRow({ run, isExpanded, onToggle }: { run: RunDetail; isExpanded: boolean; onToggle: () => void }) {
  const summary = run.output_data && typeof run.output_data === 'object'
    ? (run.output_data as Record<string, unknown>).summary as string || null
    : null;
  const actions = run.output_data && typeof run.output_data === 'object'
    ? (run.output_data as Record<string, unknown>).actions as unknown[] || []
    : [];

  return (
    <div className="border-b border-mc-border/50 dark:border-gray-800/50 last:border-0">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 py-2.5 text-left cursor-pointer bg-transparent"
      >
        <span className={clsx('w-2 h-2 rounded-full shrink-0',
          run.status === 'completed' ? 'bg-mc-green' :
          run.status === 'failed' ? 'bg-mc-red' :
          run.status === 'running' ? 'bg-mc-yellow animate-pulse' : 'bg-gray-300'
        )} />
        <span className="text-xs text-mc-text dark:text-gray-300 flex-1">
          {new Date(run.started_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
        </span>
        <Badge variant={run.status === 'completed' ? 'success' : run.status === 'failed' ? 'error' : 'warning'}>{run.status}</Badge>
        <span className="text-xs font-mono text-mc-dim">${run.cost_usd.toFixed(4)}</span>
        {(summary || run.error) ? (
          isExpanded ? <ChevronDown size={12} className="text-mc-dim" /> : <ChevronRight size={12} className="text-mc-dim" />
        ) : <span className="w-3" />}
      </button>
      {isExpanded && (summary || run.error) && (
        <div className="pl-5 pb-3 space-y-2">
          {run.error && (
            <div className="text-xs text-mc-red dark:text-mc-red bg-mc-red-bg dark:bg-mc-red-bg-dark/50 rounded-lg px-3 py-2">
              {run.error}
            </div>
          )}
          {summary && (
            <div className="text-xs text-mc-muted dark:text-gray-400 bg-gray-50 dark:bg-gray-800/50 rounded-lg px-3 py-2 whitespace-pre-wrap">
              {summary}
            </div>
          )}
          {actions.length > 0 && (
            <div className="text-[11px] text-mc-dim">
              {actions.length} action{actions.length > 1 ? 's' : ''} executed
            </div>
          )}
          {run.completed_at && (
            <div className="text-[11px] text-mc-dim">
              Duration: {Math.round((new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000)}s
              {run.tokens_used > 0 && ` · ${run.tokens_used.toLocaleString()} tokens`}
            </div>
          )}
          {run.transcript && run.transcript.length > 0 && (
            <details className="mt-2">
              <summary className="text-[11px] text-mc-accent cursor-pointer hover:underline">
                Show transcript ({run.transcript.length} messages)
              </summary>
              <div className="mt-2 space-y-1.5 max-h-64 overflow-y-auto">
                {run.transcript.map((msg, i) => (
                  <div key={i} className={clsx(
                    'text-xs px-2.5 py-1.5 rounded',
                    msg.role === 'assistant' ? 'bg-blue-50 dark:bg-blue-950/30 text-mc-text dark:text-gray-300' :
                    msg.role === 'result' ? 'bg-mc-green-bg dark:bg-mc-green-bg-dark/30 text-mc-green-dark dark:text-mc-green' :
                    'bg-gray-50 dark:bg-gray-800/50 text-mc-muted dark:text-gray-400'
                  )}>
                    <span className="font-medium text-[10px] uppercase text-mc-dim mr-1.5">{msg.role}</span>
                    <span className="whitespace-pre-wrap">{msg.content}</span>
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

export default function AgentsPage() {
  const [agents, setAgents] = useState<api.Agent[]>([]);
  const analytics: any = null; // analytics removed
  const [loading, setLoading] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [runningIds, setRunningIds] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [detailedRuns, setDetailedRuns] = useState<RunDetail[]>([]);
  const [expandedRun, setExpandedRun] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const a = await api.agents.list();
      setAgents(a);
      // Clear running IDs for agents that are no longer running
      setRunningIds((prev) => {
        const stillRunning = new Set<string>();
        for (const agent of a) {
          if (agent.status === 'running' && prev.has(agent.id)) {
            stillRunning.add(agent.id);
          }
        }
        return stillRunning;
      });
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Poll faster (5s) when agents are running, otherwise 15s
  useEffect(() => {
    const hasRunning = agents.some((a) => a.status === 'running') || runningIds.size > 0;
    const interval = hasRunning ? 5000 : 15000;
    const i = setInterval(loadData, interval);
    return () => clearInterval(i);
  }, [loadData, agents, runningIds]);

  // Load detailed runs when agent is selected
  useEffect(() => {
    if (!selectedAgent) { setDetailedRuns([]); return; }
    api.agents.runs(selectedAgent, 20).then((runs) => setDetailedRuns(runs as RunDetail[])).catch(() => {});
  }, [selectedAgent, agents]);

  // WebSocket for live agent status updates
  useEffect(() => {
    const ws = api.connectWebSocket((event) => {
      if (event.type === 'agent.started' || event.type === 'agent.completed' || event.type === 'agent.failed') {
        loadData();
        // Reload runs if this is the selected agent
        if (selectedAgent && event.data?.agent_id === selectedAgent) {
          api.agents.runs(selectedAgent, 20).then((runs) => setDetailedRuns(runs as RunDetail[])).catch(() => {});
        }
      }
    });
    return () => { ws?.close(); };
  }, [loadData, selectedAgent]);

  const triggerAgent = async (id: string) => {
    const agent = agents.find((a) => a.id === id);
    if (!agent) return;

    // Optimistic: show running state immediately
    setRunningIds((prev) => new Set(prev).add(id));
    setAgents((prev) => prev.map((a) => a.id === id ? { ...a, status: 'running' as const } : a));

    try {
      await api.agents.run(id);
      setToast({ message: `${agent.name} started`, type: 'success' });
    } catch (err) {
      // Rollback
      setRunningIds((prev) => { const next = new Set(prev); next.delete(id); return next; });
      setAgents((prev) => prev.map((a) => a.id === id ? { ...a, status: 'idle' as const } : a));
      setToast({ message: `Failed to start ${agent.name}: ${err instanceof Error ? err.message : 'Unknown error'}`, type: 'error' });
    }
  };

  const stopAgent = async (id: string) => {
    try {
      await api.agents.stop(id);
      setRunningIds((prev) => { const next = new Set(prev); next.delete(id); return next; });
      loadData();
    } catch {}
  };

  const handleExpandRun = async (run: RunDetail) => {
    if (expandedRun === run.id) {
      setExpandedRun(null);
      return;
    }
    setExpandedRun(run.id);
    // Lazy-load transcript if not yet fetched
    if (!run.transcript && selectedAgent) {
      try {
        const detail = await api.agents.runDetail(selectedAgent, run.id);
        setDetailedRuns((prev) => prev.map((r) =>
          r.id === run.id ? { ...r, transcript: (detail as unknown as RunDetail).transcript } : r
        ));
      } catch {}
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-mc-bg dark:bg-gray-950 flex items-center justify-center">
        <Loader2 size={24} className="text-mc-accent animate-spin" />
      </div>
    );
  }

  const totals = analytics?.totals;
  const selected = selectedAgent ? agents.find((a) => a.id === selectedAgent) : null;
  const selectedAnalytics = analytics?.agents.find((a: { agent_id: string }) => a.agent_id === selectedAgent);

  return (
    <Tooltip.Provider delayDuration={200}>
      <div className="min-h-screen bg-mc-bg dark:bg-gray-950 transition-colors">
        {toast && <Toast message={toast.message} type={toast.type} onDone={() => setToast(null)} />}

        <header className="px-4 sm:px-6 lg:px-8 py-3 bg-white dark:bg-gray-900 border-b border-mc-border dark:border-gray-800 sticky top-0 z-30">
          <div className="max-w-[1600px] mx-auto flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Zap size={18} className="text-mc-accent" />
              <h1 className="text-base font-bold text-mc-text dark:text-gray-100">Agents</h1>
              <span className="text-xs text-mc-dim">{agents.length} configured</span>
            </div>
            <Link href="/agents/new" className="flex items-center gap-1.5 px-3 py-1.5 bg-mc-accent text-white text-sm rounded-lg hover:bg-mc-accent-hover transition-colors">
              <Plus size={14} /> Create Agent
            </Link>
          </div>
        </header>

        <main className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {/* Overview stats */}
          {totals && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
              <Card className="p-4 text-center">
                <div className="text-xl font-bold text-mc-text dark:text-gray-100">{totals.total_runs}</div>
                <div className="text-[11px] text-mc-dim">Total Runs</div>
              </Card>
              <Card className="p-4 text-center">
                <div className={clsx('text-xl font-bold', totals.overall_success_rate >= 80 ? 'text-mc-green' : 'text-mc-yellow')}>
                  {Math.round(totals.overall_success_rate)}%
                </div>
                <div className="text-[11px] text-mc-dim">Success Rate</div>
              </Card>
              <Card className="p-4 text-center">
                <div className="text-xl font-bold text-mc-text dark:text-gray-100 font-mono">${totals.total_cost_usd.toFixed(2)}</div>
                <div className="text-[11px] text-mc-dim">Total Cost</div>
              </Card>
              <Card className="p-4 text-center">
                <div className="text-xl font-bold text-mc-accent">{agents.filter((a) => a.status === 'running').length}</div>
                <div className="text-[11px] text-mc-dim">Running Now</div>
              </Card>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Agent List */}
            <div className="flex flex-col gap-2">
              <h2 className="text-xs font-semibold text-mc-dim uppercase tracking-wide mb-1">All Agents</h2>
              {agents.map((a) => {
                const isSelected = selectedAgent === a.id;
                const agentAnalytics = analytics?.agents.find((an: { agent_id: string }) => an.agent_id === a.id);
                const isStarting = runningIds.has(a.id) && a.status !== 'running';
                return (
                  <button
                    key={a.id}
                    onClick={() => setSelectedAgent(isSelected ? null : a.id)}
                    className={clsx(
                      'w-full text-left p-3.5 rounded-xl border transition-all cursor-pointer bg-white dark:bg-gray-900',
                      isSelected
                        ? 'border-mc-accent shadow-md ring-2 ring-mc-accent/10'
                        : 'border-mc-border dark:border-gray-800 hover:shadow-card-hover'
                    )}
                  >
                    <div className="flex items-center gap-2.5 mb-1.5">
                      <StatusIndicator status={a.status} />
                      <span className="text-sm font-semibold text-mc-text dark:text-gray-100 truncate flex-1">{a.name}</span>
                      <Link
                        href={`/agents/${a.id}/edit`}
                        onClick={(e) => e.stopPropagation()}
                        className="text-mc-muted hover:text-mc-text dark:hover:text-gray-300 transition-colors"
                      >
                        <Pencil size={14} />
                      </Link>
                      <button
                        onClick={(e) => { e.stopPropagation(); a.status === 'running' ? stopAgent(a.id) : triggerAgent(a.id); }}
                        disabled={isStarting}
                        className={clsx(
                          'w-7 h-7 rounded-lg flex items-center justify-center transition-all cursor-pointer border',
                          a.status === 'running'
                            ? 'bg-mc-red-bg dark:bg-mc-red-bg-dark border-mc-red-light dark:border-mc-red-dark text-mc-red hover:bg-mc-red-light'
                            : 'bg-mc-green-bg dark:bg-mc-green-bg-dark border-mc-green-light dark:border-mc-green-dark text-mc-green hover:bg-mc-green-light',
                          isStarting && 'opacity-60'
                        )}
                      >
                        {isStarting ? <Loader2 size={12} className="animate-spin" /> :
                         a.status === 'running' ? <Square size={12} /> : <Play size={12} />}
                      </button>
                    </div>
                    {a.status === 'running' && (
                      <div className="flex items-center gap-2 mb-2">
                        <div className="flex-1 h-1 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                          <div className="h-full bg-mc-accent rounded-full animate-pulse" style={{ width: '60%' }} />
                        </div>
                        <span className="text-[10px] text-mc-accent font-medium">Running</span>
                      </div>
                    )}
                    <p className="text-xs text-mc-muted dark:text-gray-500 truncate mb-2">{a.description}</p>
                    <div className="flex items-center gap-2 text-[11px] text-mc-dim">
                      <Badge variant={a.agent_type === 'research' ? 'purple' : a.agent_type === 'ops' ? 'blue' : 'default'}>{a.agent_type}</Badge>
                      <span className="font-mono">{a.model}</span>
                      {agentAnalytics && <span className="ml-auto font-mono">${agentAnalytics.total_cost_usd.toFixed(3)}</span>}
                    </div>
                  </button>
                );
              })}
              {agents.length === 0 && <EmptyState icon={Zap} message="No agents configured" />}
            </div>

            {/* Agent Detail */}
            <div className="lg:col-span-2">
              {selected ? (
                <div className="flex flex-col gap-4">
                  <div className="flex items-center gap-3 mb-2">
                    <StatusIndicator status={selected.status} />
                    <h2 className="text-lg font-bold text-mc-text dark:text-gray-100">{selected.name}</h2>
                    <Badge>{selected.agent_type}</Badge>
                    <span className="text-xs text-mc-dim font-mono ml-auto">{selected.model}</span>
                  </div>
                  <p className="text-sm text-mc-muted dark:text-gray-400">{selected.description}</p>

                  {/* Schedule info */}
                  <Card className="p-4">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                      <div>
                        <Clock size={16} className="text-mc-muted mx-auto mb-1" />
                        <div className="text-sm font-semibold text-mc-text dark:text-gray-100">{selected.schedule_type || 'manual'}</div>
                        <div className="text-[11px] text-mc-dim">{selected.schedule_value || 'On demand'}</div>
                      </div>
                      <div>
                        <Activity size={16} className="text-mc-muted mx-auto mb-1" />
                        <div className="text-sm font-semibold text-mc-text dark:text-gray-100">{selectedAnalytics?.total_runs || 0}</div>
                        <div className="text-[11px] text-mc-dim">Total Runs</div>
                      </div>
                      <div>
                        <TrendingUp size={16} className="text-mc-muted mx-auto mb-1" />
                        <div className={clsx('text-sm font-semibold', (selectedAnalytics?.success_rate ?? 100) >= 80 ? 'text-mc-green' : 'text-mc-yellow')}>
                          {Math.round(selectedAnalytics?.success_rate ?? 100)}%
                        </div>
                        <div className="text-[11px] text-mc-dim">Success Rate</div>
                      </div>
                      <div>
                        <DollarSign size={16} className="text-mc-muted mx-auto mb-1" />
                        <div className="text-sm font-semibold text-mc-text dark:text-gray-100 font-mono">
                          ${(selectedAnalytics?.total_cost_usd ?? 0).toFixed(3)}
                        </div>
                        <div className="text-[11px] text-mc-dim">Total Cost</div>
                      </div>
                    </div>
                  </Card>

                  {/* Daily cost chart */}
                  {selectedAnalytics && Object.keys(selectedAnalytics.daily_costs).length > 0 && (
                    <Card className="p-4">
                      <h3 className="text-sm font-semibold text-mc-text dark:text-gray-100 mb-3">Daily Cost (14d)</h3>
                      <div className="flex items-end gap-1 h-24">
                        {Object.entries(selectedAnalytics.daily_costs).slice(-14).map(([day, cost]) => {
                          const costNum = cost as number;
                          const maxCost = Math.max(...(Object.values(selectedAnalytics.daily_costs) as number[]), 0.01);
                          const h = Math.max(4, (costNum / maxCost) * 96);
                          return (
                            <Tooltip.Root key={day}>
                              <Tooltip.Trigger asChild>
                                <div className="flex-1 rounded-t bg-mc-accent/60 dark:bg-blue-500/40 hover:bg-mc-accent transition-colors cursor-default" style={{ height: `${h}px` }} />
                              </Tooltip.Trigger>
                              <Tooltip.Content className="bg-mc-text text-white text-xs px-2 py-1 rounded-md" sideOffset={5}>
                                {day}: ${costNum.toFixed(4)}
                              </Tooltip.Content>
                            </Tooltip.Root>
                          );
                        })}
                      </div>
                    </Card>
                  )}

                  {/* Recent runs with expandable details */}
                  <Card className="p-4">
                    <h3 className="text-sm font-semibold text-mc-text dark:text-gray-100 mb-3">Recent Runs</h3>
                    <div className="flex flex-col">
                      {detailedRuns.slice(0, 15).map((r) => (
                        <RunRow
                          key={r.id}
                          run={r}
                          isExpanded={expandedRun === r.id}
                          onToggle={() => handleExpandRun(r)}
                        />
                      ))}
                      {detailedRuns.length === 0 && <span className="text-xs text-mc-dim py-2">No runs yet</span>}
                    </div>
                  </Card>
                </div>
              ) : (
                <div className="flex items-center justify-center h-64">
                  <EmptyState icon={Zap} message="Select an agent to see details" />
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </Tooltip.Provider>
  );
}
