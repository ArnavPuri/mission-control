'use client';

import { useState, useEffect, useCallback } from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import {
  Megaphone, Radio, FileText, Copy, Check, ExternalLink,
  Eye, X, Send, Loader2,
} from 'lucide-react';
import { clsx } from 'clsx';
import { Card, Badge, EmptyState } from '../components/shared';
import {
  fetchSignals, fetchContent, updateSignal, updateContent,
  createContent, fetchMarketingStats,
  MarketingSignal, MarketingContent,
} from '../lib/api';

function timeAgo(dateStr: string): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

const SOURCE_BADGE: Record<string, 'purple' | 'blue' | 'warning' | 'default'> = {
  reddit: 'purple',
  twitter: 'blue',
  hackernews: 'warning',
};

const SIGNAL_TYPE_BADGE: Record<string, 'success' | 'warning' | 'error' | 'blue'> = {
  opportunity: 'success',
  feedback: 'warning',
  competitor: 'error',
  trend: 'blue',
};

type Stats = {
  signals: { by_status: Record<string, number>; by_type: Record<string, number>; total: number };
  content: { by_status: Record<string, number>; by_channel: Record<string, number>; total: number };
};

export default function MarketingPage() {
  const [signals, setSignals] = useState<MarketingSignal[]>([]);
  const [content, setContent] = useState<MarketingContent[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [signalFilter, setSignalFilter] = useState<string>('all');
  const [contentTab, setContentTab] = useState<string>('draft');
  const [copied, setCopied] = useState<string | null>(null);
  const [postUrlInput, setPostUrlInput] = useState<Record<string, string>>({});

  const loadData = useCallback(async () => {
    try {
      const [s, c, st] = await Promise.all([
        fetchSignals(signalFilter !== 'all' ? { status: signalFilter } : undefined),
        fetchContent(),
        fetchMarketingStats().catch(() => null),
      ]);
      setSignals(s);
      setContent(c);
      setStats(st);
    } catch {} finally { setLoading(false); }
  }, [signalFilter]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSignalStatus = async (id: string, status: string) => {
    try { await updateSignal(id, { status: status as MarketingSignal['status'] }); loadData(); } catch {}
  };

  const handleCreateDraft = async (signal: MarketingSignal) => {
    try {
      await createContent({
        title: `Re: ${signal.title}`,
        body: '',
        channel: signal.source_type === 'reddit' ? 'reddit_comment' : signal.source_type === 'twitter' ? 'twitter_tweet' : 'other',
        status: 'draft',
        signal_id: signal.id,
        source: 'dashboard',
      });
      loadData();
    } catch {}
  };

  const handleContentStatus = async (id: string, status: string, postedUrl?: string) => {
    try {
      const data: Partial<MarketingContent> = { status: status as MarketingContent['status'] };
      if (postedUrl) data.posted_url = postedUrl;
      await updateContent(id, data);
      loadData();
    } catch {}
  };

  const copyToClipboard = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-mc-bg dark:bg-gray-950 flex items-center justify-center">
        <Loader2 size={24} className="text-mc-accent animate-spin" />
      </div>
    );
  }

  const filteredContent = content.filter((c) => c.status === contentTab);
  const signalMap = new Map(signals.map((s) => [s.id, s]));

  const newCount = stats?.signals.by_status?.new ?? 0;
  const draftsCount = stats?.content.by_status?.draft ?? 0;
  const postedCount = stats?.content.by_status?.posted ?? 0;

  return (
    <div className="min-h-screen bg-mc-bg dark:bg-gray-950 transition-colors">
      <header className="px-4 sm:px-6 lg:px-8 py-3 bg-white dark:bg-gray-900 border-b border-mc-border dark:border-gray-800 sticky top-0 z-30">
        <div className="max-w-[1600px] mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Megaphone size={18} className="text-mc-accent" />
            <h1 className="text-base font-bold text-mc-text dark:text-gray-100">Marketing</h1>
            <span className="text-xs text-mc-dim">{stats?.signals.total ?? 0} signals, {stats?.content.total ?? 0} content</span>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Stats Bar */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          <Card className="p-4 text-center">
            <div className="text-xl font-bold text-mc-accent">{newCount}</div>
            <div className="text-[11px] text-mc-dim">New Signals</div>
          </Card>
          <Card className="p-4 text-center">
            <div className="text-xl font-bold text-amber-600 dark:text-amber-400">{draftsCount}</div>
            <div className="text-[11px] text-mc-dim">Drafts Ready</div>
          </Card>
          <Card className="p-4 text-center">
            <div className="text-xl font-bold text-emerald-600 dark:text-emerald-400">{postedCount}</div>
            <div className="text-[11px] text-mc-dim">Posted</div>
          </Card>
        </div>

        {/* Two Panel Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Panel — Signals */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Radio size={15} className="text-mc-muted dark:text-gray-500" />
                <h2 className="text-sm font-semibold text-mc-text dark:text-gray-100">Signals</h2>
                <span className="text-xs text-mc-dim font-medium">{signals.length}</span>
              </div>
              <select
                value={signalFilter}
                onChange={(e) => { setSignalFilter(e.target.value); setLoading(true); }}
                className="text-xs border border-mc-border dark:border-gray-700 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-800 text-mc-text dark:text-gray-200 outline-none focus:border-mc-accent cursor-pointer"
              >
                <option value="all">All</option>
                <option value="new">New</option>
                <option value="reviewed">Reviewed</option>
                <option value="acted_on">Acted On</option>
                <option value="dismissed">Dismissed</option>
              </select>
            </div>

            <div className="flex flex-col gap-2">
              {signals.map((s) => {
                const relevanceColor = s.relevance_score > 0.7 ? 'bg-emerald-500' : s.relevance_score >= 0.4 ? 'bg-amber-400' : 'bg-gray-300 dark:bg-gray-600';
                return (
                  <Card key={s.id} className="p-3.5">
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      {s.source_url ? (
                        <a
                          href={s.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-semibold text-mc-text dark:text-gray-100 line-clamp-2 hover:text-mc-accent transition-colors flex items-center gap-1"
                        >
                          {s.title}
                          <ExternalLink size={12} className="shrink-0 text-mc-dim" />
                        </a>
                      ) : (
                        <span className="text-sm font-semibold text-mc-text dark:text-gray-100 line-clamp-2">{s.title}</span>
                      )}
                      <span className="text-[11px] text-mc-dim whitespace-nowrap shrink-0">{timeAgo(s.created_at)}</span>
                    </div>

                    <div className="flex items-center gap-1.5 flex-wrap mb-2">
                      <Badge variant={SOURCE_BADGE[s.source_type] ?? 'default'}>{s.source_type}</Badge>
                      <Badge variant={SIGNAL_TYPE_BADGE[s.signal_type] ?? 'default'}>{s.signal_type}</Badge>
                      <div className="flex items-center gap-1 ml-auto">
                        <div className="w-16 h-1.5 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
                          <div className={clsx('h-full rounded-full', relevanceColor)} style={{ width: `${Math.round(s.relevance_score * 100)}%` }} />
                        </div>
                        <span className="text-[10px] text-mc-dim font-mono">{(s.relevance_score * 100).toFixed(0)}%</span>
                      </div>
                    </div>

                    {s.status === 'new' && (
                      <div className="flex items-center gap-1.5 pt-1 border-t border-mc-border/50 dark:border-gray-800/50">
                        <button
                          onClick={() => handleSignalStatus(s.id, 'reviewed')}
                          className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-mc-muted dark:text-gray-400 bg-gray-50 dark:bg-gray-800 border border-mc-border dark:border-gray-700 rounded-md hover:bg-blue-50 hover:text-blue-600 dark:hover:bg-blue-950 dark:hover:text-blue-400 transition-colors cursor-pointer"
                        >
                          <Eye size={12} /> Mark Reviewed
                        </button>
                        <button
                          onClick={() => handleSignalStatus(s.id, 'dismissed')}
                          className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-mc-muted dark:text-gray-400 bg-gray-50 dark:bg-gray-800 border border-mc-border dark:border-gray-700 rounded-md hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950 dark:hover:text-red-400 transition-colors cursor-pointer"
                        >
                          <X size={12} /> Dismiss
                        </button>
                        <button
                          onClick={() => handleCreateDraft(s)}
                          className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-white bg-mc-accent rounded-md hover:bg-blue-700 transition-colors cursor-pointer ml-auto"
                        >
                          <FileText size={12} /> Create Draft
                        </button>
                      </div>
                    )}
                    {s.status === 'reviewed' && (
                      <div className="flex items-center gap-1.5 pt-1 border-t border-mc-border/50 dark:border-gray-800/50">
                        <button
                          onClick={() => handleCreateDraft(s)}
                          className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-white bg-mc-accent rounded-md hover:bg-blue-700 transition-colors cursor-pointer"
                        >
                          <FileText size={12} /> Create Draft
                        </button>
                        <button
                          onClick={() => handleSignalStatus(s.id, 'dismissed')}
                          className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-mc-muted dark:text-gray-400 bg-gray-50 dark:bg-gray-800 border border-mc-border dark:border-gray-700 rounded-md hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950 dark:hover:text-red-400 transition-colors cursor-pointer"
                        >
                          <X size={12} /> Dismiss
                        </button>
                      </div>
                    )}
                  </Card>
                );
              })}
              {signals.length === 0 && <EmptyState icon={Radio} message="No signals found" />}
            </div>
          </div>

          {/* Right Panel — Content */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <FileText size={15} className="text-mc-muted dark:text-gray-500" />
              <h2 className="text-sm font-semibold text-mc-text dark:text-gray-100">Content</h2>
              <span className="text-xs text-mc-dim font-medium">{content.length}</span>
            </div>

            <Tabs.Root value={contentTab} onValueChange={setContentTab}>
              <Tabs.List className="flex gap-0 mb-3 bg-gray-100 dark:bg-gray-800 rounded-lg p-0.5">
                {[
                  { value: 'draft', label: 'Drafts' },
                  { value: 'approved', label: 'Approved' },
                  { value: 'posted', label: 'Posted' },
                ].map((tab) => (
                  <Tabs.Trigger
                    key={tab.value}
                    value={tab.value}
                    className={clsx(
                      'flex-1 px-3 py-1.5 text-xs font-medium rounded-md transition-colors cursor-pointer',
                      contentTab === tab.value
                        ? 'bg-white dark:bg-gray-900 text-mc-text dark:text-gray-100 shadow-sm'
                        : 'text-mc-muted dark:text-gray-500 hover:text-mc-text dark:hover:text-gray-300'
                    )}
                  >
                    {tab.label}
                    <span className="ml-1 text-[10px] text-mc-dim">
                      {content.filter((c) => c.status === tab.value).length}
                    </span>
                  </Tabs.Trigger>
                ))}
              </Tabs.List>

              {['draft', 'approved', 'posted'].map((tabVal) => (
                <Tabs.Content key={tabVal} value={tabVal} className="flex flex-col gap-2">
                  {content.filter((c) => c.status === tabVal).map((c) => {
                    const linkedSignal = c.signal_id ? signalMap.get(c.signal_id) : null;
                    return (
                      <Card key={c.id} className="p-3.5">
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <span className="text-sm font-semibold text-mc-text dark:text-gray-100 line-clamp-1">{c.title}</span>
                          <Badge variant="default">{c.channel}</Badge>
                        </div>

                        {c.body && (
                          <p className="text-xs text-mc-muted dark:text-gray-400 mb-2 line-clamp-3">
                            {c.body.length > 150 ? c.body.slice(0, 150) + '...' : c.body}
                          </p>
                        )}

                        {linkedSignal && (
                          <div className="text-[11px] text-mc-dim mb-2 flex items-center gap-1">
                            <Radio size={10} />
                            <span className="truncate">Signal: {linkedSignal.title}</span>
                          </div>
                        )}

                        {tabVal === 'draft' && (
                          <div className="flex items-center gap-1.5 pt-1 border-t border-mc-border/50 dark:border-gray-800/50">
                            <button
                              onClick={() => handleContentStatus(c.id, 'approved')}
                              className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-white bg-emerald-600 rounded-md hover:bg-emerald-700 transition-colors cursor-pointer"
                            >
                              <Check size={12} /> Approve
                            </button>
                            <button
                              onClick={() => copyToClipboard(c.id, c.body)}
                              className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-mc-muted dark:text-gray-400 bg-gray-50 dark:bg-gray-800 border border-mc-border dark:border-gray-700 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors cursor-pointer"
                            >
                              {copied === c.id ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                              {copied === c.id ? 'Copied' : 'Copy'}
                            </button>
                          </div>
                        )}

                        {tabVal === 'approved' && (
                          <div className="flex items-center gap-1.5 pt-1 border-t border-mc-border/50 dark:border-gray-800/50">
                            <input
                              type="text"
                              placeholder="Posted URL..."
                              value={postUrlInput[c.id] || ''}
                              onChange={(e) => setPostUrlInput((prev) => ({ ...prev, [c.id]: e.target.value }))}
                              className="flex-1 text-[11px] border border-mc-border dark:border-gray-700 rounded-md px-2 py-1 bg-white dark:bg-gray-800 text-mc-text dark:text-gray-200 outline-none focus:border-mc-accent placeholder:text-mc-dim"
                            />
                            <button
                              onClick={() => handleContentStatus(c.id, 'posted', postUrlInput[c.id] || undefined)}
                              className="flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-white bg-mc-accent rounded-md hover:bg-blue-700 transition-colors cursor-pointer"
                            >
                              <Send size={12} /> Mark Posted
                            </button>
                          </div>
                        )}

                        {tabVal === 'posted' && c.posted_url && (
                          <div className="pt-1 border-t border-mc-border/50 dark:border-gray-800/50">
                            <a
                              href={c.posted_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1 text-[11px] text-mc-accent hover:underline"
                            >
                              <ExternalLink size={11} /> {c.posted_url}
                            </a>
                          </div>
                        )}
                      </Card>
                    );
                  })}
                  {content.filter((c) => c.status === tabVal).length === 0 && (
                    <EmptyState icon={FileText} message={`No ${tabVal} content`} />
                  )}
                </Tabs.Content>
              ))}
            </Tabs.Root>
          </div>
        </div>
      </main>
    </div>
  );
}
