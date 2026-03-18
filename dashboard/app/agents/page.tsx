'use client';

import { useState, useEffect, useCallback } from 'react';
import * as api from '../lib/api';
import * as Progress from '@radix-ui/react-progress';
import * as Tooltip from '@radix-ui/react-tooltip';
import {
  Zap, Play, Square, Clock, DollarSign, Activity,
  BarChart3, Loader2, TrendingUp, AlertTriangle, Plus, Pencil,
} from 'lucide-react';
import { clsx } from 'clsx';
import Link from 'next/link';
import { Card, Badge, StatusIndicator, EmptyState } from '../components/shared';

export default function AgentsPage() {
  const [agents, setAgents] = useState<api.Agent[]>([]);
  const [analytics, setAnalytics] = useState<api.AgentAnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [a, an] = await Promise.all([
        api.agents.list(),
        api.agentAnalytics.overview().catch(() => null),
      ]);
      setAgents(a);
      setAnalytics(an);
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => { const i = setInterval(loadData, 15000); return () => clearInterval(i); }, [loadData]);

  const toggleAgent = async (id: string, action: 'run' | 'stop') => {
    try {
      if (action === 'run') await api.agents.run(id); else await api.agents.stop(id);
      loadData();
    } catch {}
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
  const selectedAnalytics = analytics?.agents.find((a) => a.agent_id === selectedAgent);

  return (
    <Tooltip.Provider delayDuration={200}>
      <div className="min-h-screen bg-mc-bg dark:bg-gray-950 transition-colors">
        <header className="px-4 sm:px-6 lg:px-8 py-3 bg-white dark:bg-gray-900 border-b border-mc-border dark:border-gray-800 sticky top-0 z-30">
          <div className="max-w-[1600px] mx-auto flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Zap size={18} className="text-mc-accent" />
              <h1 className="text-base font-bold text-mc-text dark:text-gray-100">Agents</h1>
              <span className="text-xs text-mc-dim">{agents.length} configured</span>
            </div>
            <Link href="/agents/new" className="flex items-center gap-1.5 px-3 py-1.5 bg-mc-accent text-white text-sm rounded-lg hover:bg-blue-700 transition-colors">
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
                <div className={clsx('text-xl font-bold', totals.overall_success_rate >= 80 ? 'text-emerald-600' : 'text-amber-600')}>
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
                const agentAnalytics = analytics?.agents.find((an) => an.agent_id === a.id);
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
                        onClick={(e) => { e.stopPropagation(); toggleAgent(a.id, a.status === 'running' ? 'stop' : 'run'); }}
                        className={clsx(
                          'w-7 h-7 rounded-lg flex items-center justify-center transition-all cursor-pointer border',
                          a.status === 'running'
                            ? 'bg-red-50 dark:bg-red-950 border-red-200 dark:border-red-800 text-red-600 hover:bg-red-100'
                            : 'bg-emerald-50 dark:bg-emerald-950 border-emerald-200 dark:border-emerald-800 text-emerald-600 hover:bg-emerald-100'
                        )}
                      >
                        {a.status === 'running' ? <Square size={12} /> : <Play size={12} />}
                      </button>
                    </div>
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
                        <div className={clsx('text-sm font-semibold', (selectedAnalytics?.success_rate ?? 100) >= 80 ? 'text-emerald-600' : 'text-amber-600')}>
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
                          const maxCost = Math.max(...Object.values(selectedAnalytics.daily_costs), 0.01);
                          const h = Math.max(4, (cost / maxCost) * 96);
                          return (
                            <Tooltip.Root key={day}>
                              <Tooltip.Trigger asChild>
                                <div className="flex-1 rounded-t bg-mc-accent/60 dark:bg-blue-500/40 hover:bg-mc-accent transition-colors cursor-default" style={{ height: `${h}px` }} />
                              </Tooltip.Trigger>
                              <Tooltip.Content className="bg-mc-text text-white text-xs px-2 py-1 rounded-md" sideOffset={5}>
                                {day}: ${cost.toFixed(4)}
                              </Tooltip.Content>
                            </Tooltip.Root>
                          );
                        })}
                      </div>
                    </Card>
                  )}

                  {/* Recent runs */}
                  <Card className="p-4">
                    <h3 className="text-sm font-semibold text-mc-text dark:text-gray-100 mb-3">Recent Runs</h3>
                    <div className="flex flex-col gap-2">
                      {selected.recent_runs.slice(0, 10).map((r) => (
                        <div key={r.id} className="flex items-center gap-3 py-2 border-b border-mc-border/50 dark:border-gray-800/50 last:border-0">
                          <span className={clsx('w-2 h-2 rounded-full shrink-0', r.status === 'completed' ? 'bg-emerald-500' : r.status === 'failed' ? 'bg-red-500' : 'bg-amber-400')} />
                          <span className="text-xs text-mc-text dark:text-gray-300 flex-1">
                            {new Date(r.started_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                          </span>
                          <Badge variant={r.status === 'completed' ? 'success' : r.status === 'failed' ? 'error' : 'warning'}>{r.status}</Badge>
                          <span className="text-xs font-mono text-mc-dim">${r.cost_usd.toFixed(4)}</span>
                        </div>
                      ))}
                      {selected.recent_runs.length === 0 && <span className="text-xs text-mc-dim py-2">No runs yet</span>}
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
