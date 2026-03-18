'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { Zap, Play, ChevronDown, ChevronRight, Loader2, AlertCircle } from 'lucide-react';
import { clsx } from 'clsx';
import * as api from '../../../lib/api';
import { AgentBuilderForm } from '../../builder-form';
import { Card } from '../../../components/shared';

// ─── Dry Run Result Panel ─────────────────────────────────

interface DryRunResult {
  model?: string;
  prompt_length?: number;
  prompt_preview?: string;
  context_keys?: string[];
  context_sizes?: Record<string, number>;
  tools?: string[];
  [key: string]: unknown;
}

function DryRunPanel({ agentId }: { agentId: string }) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<DryRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(true);

  const handleDryRun = async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const data = await api.agents.dryRun(agentId);
      setResult(data as DryRunResult);
      setExpanded(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Dry run failed');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="border-t border-mc-border dark:border-gray-800 pt-6 mt-2">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-bold text-mc-text dark:text-gray-100 flex items-center gap-2">
          <Play size={14} className="text-mc-accent" />
          Test Run
        </h2>
        <button
          onClick={handleDryRun}
          disabled={running}
          className={clsx(
            'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white rounded-lg transition-colors cursor-pointer',
            running ? 'bg-mc-accent/60 cursor-not-allowed' : 'bg-mc-accent hover:bg-blue-700',
          )}
        >
          {running ? (
            <><Loader2 size={12} className="animate-spin" /> Running…</>
          ) : (
            <><Play size={12} /> Dry Run</>
          )}
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-xl text-sm text-red-700 dark:text-red-400">
          <AlertCircle size={14} /> {error}
        </div>
      )}

      {result && (
        <Card className="overflow-hidden">
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-mc-text dark:text-gray-100 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors cursor-pointer"
          >
            <span>Dry Run Result</span>
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>

          {expanded && (
            <div className="px-4 pb-4 space-y-4 border-t border-mc-border dark:border-gray-800">
              {/* Model */}
              {result.model && (
                <div className="pt-3">
                  <div className="text-[11px] font-semibold text-mc-dim uppercase tracking-wide mb-1">Model</div>
                  <div className="text-sm text-mc-text dark:text-gray-200 font-mono">{result.model}</div>
                </div>
              )}

              {/* Prompt Length */}
              {result.prompt_length !== undefined && (
                <div>
                  <div className="text-[11px] font-semibold text-mc-dim uppercase tracking-wide mb-1">Prompt Length</div>
                  <div className="text-sm text-mc-text dark:text-gray-200 font-mono">
                    {result.prompt_length.toLocaleString()} chars
                  </div>
                </div>
              )}

              {/* Context Keys & Sizes */}
              {result.context_keys && result.context_keys.length > 0 && (
                <div>
                  <div className="text-[11px] font-semibold text-mc-dim uppercase tracking-wide mb-2">Context</div>
                  <div className="flex flex-wrap gap-1.5">
                    {result.context_keys.map((key) => (
                      <span
                        key={key}
                        className="inline-flex items-center gap-1 px-2 py-0.5 bg-mc-accent/5 dark:bg-blue-950/50 border border-mc-accent/20 dark:border-blue-800 rounded text-[11px] font-mono text-mc-accent dark:text-blue-400"
                      >
                        {key}
                        {result.context_sizes?.[key] !== undefined && (
                          <span className="text-mc-dim">
                            ({result.context_sizes[key].toLocaleString()} chars)
                          </span>
                        )}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Tools */}
              {result.tools && result.tools.length > 0 && (
                <div>
                  <div className="text-[11px] font-semibold text-mc-dim uppercase tracking-wide mb-2">Tools</div>
                  <div className="flex flex-wrap gap-1.5">
                    {result.tools.map((tool) => (
                      <span
                        key={tool}
                        className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 border border-mc-border dark:border-gray-700 rounded text-[11px] font-mono text-mc-muted dark:text-gray-400"
                      >
                        {tool}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Prompt Preview */}
              {result.prompt_preview && (
                <div>
                  <div className="text-[11px] font-semibold text-mc-dim uppercase tracking-wide mb-2">Prompt Preview</div>
                  <pre className="text-xs text-mc-text dark:text-gray-300 bg-gray-50 dark:bg-gray-900 border border-mc-border dark:border-gray-700 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed max-h-64">
                    <code>{result.prompt_preview}</code>
                  </pre>
                </div>
              )}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────

export default function EditAgentPage() {
  const params = useParams();
  const id = params.id as string;

  const [agent, setAgent] = useState<api.AgentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api.agents
      .get(id)
      .then(setAgent)
      .catch((err: unknown) => {
        setFetchError(err instanceof Error ? err.message : 'Failed to load agent');
      })
      .finally(() => setLoading(false));
  }, [id]);

  return (
    <div className="min-h-screen bg-mc-bg dark:bg-gray-950 transition-colors">
      <header className="px-4 sm:px-6 lg:px-8 py-3 bg-white dark:bg-gray-900 border-b border-mc-border dark:border-gray-800 sticky top-0 z-30">
        <div className="max-w-[1600px] mx-auto flex items-center gap-3">
          <Zap size={18} className="text-mc-accent" />
          <h1 className="text-base font-bold text-mc-text dark:text-gray-100">
            {loading ? 'Edit Agent' : agent ? `Edit: ${agent.name}` : 'Edit Agent'}
          </h1>
        </div>
      </header>

      <main className="max-w-[900px] mx-auto px-4 sm:px-6 lg:px-8 py-6 pb-24">
        {loading && (
          <div className="flex items-center justify-center py-24 text-mc-muted dark:text-gray-400">
            <Loader2 size={20} className="animate-spin mr-2" />
            <span className="text-sm">Loading agent…</span>
          </div>
        )}

        {fetchError && (
          <div className="flex items-center gap-2 px-4 py-3 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-xl text-sm text-red-700 dark:text-red-400">
            <AlertCircle size={14} /> {fetchError}
          </div>
        )}

        {!loading && agent && (
          <>
            <AgentBuilderForm
              initialData={agent}
              agentId={id}
              showTemplates={false}
            />
            <DryRunPanel agentId={id} />
          </>
        )}
      </main>
    </div>
  );
}
