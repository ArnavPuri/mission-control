'use client';

import { useState, useEffect, useCallback } from 'react';
import * as api from '../lib/api';
import {
  Settings, Key, Globe, Rss, Shield, Plus, X, Loader2,
  Copy, Check, ExternalLink, Trash2, Bell,
} from 'lucide-react';
import { clsx } from 'clsx';
import { Card, Badge, EmptyState, InlineInput } from '../components/shared';

export default function SettingsPage() {
  const [health, setHealth] = useState<api.HealthStatus | null>(null);
  const [apiKeysList, setApiKeys] = useState<api.ApiKeyRecord[]>([]);
  const [feedsList, setFeeds] = useState<api.RSSFeed[]>([]);
  const [reposList, setRepos] = useState<api.GitHubRepo[]>([]);
  const [loading, setLoading] = useState(true);
  const [newKeyName, setNewKeyName] = useState('');
  const [showNewKey, setShowNewKey] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState(false);
  const [showAddFeed, setShowAddFeed] = useState(false);
  const [showAddRepo, setShowAddRepo] = useState(false);
  const [activeTab, setActiveTab] = useState<'general' | 'notifications' | 'api-keys' | 'github' | 'feeds'>('general');
  const [notifPrefs, setNotifPrefs] = useState<api.NotificationPrefs | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [h, keys, feeds, repos, np] = await Promise.all([
        api.health.check(),
        api.apiKeys.list().catch(() => []),
        api.feeds.list().catch(() => []),
        api.github.repos().catch(() => []),
        api.getNotificationPrefs().catch(() => ({ agent_completions: true, agent_failures: true, signal_summary: true, content_drafts: true })),
      ]);
      setHealth(h); setApiKeys(keys); setFeeds(feeds); setRepos(repos); setNotifPrefs(np);
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const createApiKey = async () => {
    if (!newKeyName.trim()) return;
    const result = await api.apiKeys.create({ name: newKeyName.trim(), scopes: ['read', 'write'] });
    setCreatedKey(result.key);
    setNewKeyName('');
    setShowNewKey(false);
    loadData();
  };

  const revokeKey = async (id: string) => { await api.apiKeys.revoke(id); loadData(); };

  const addFeed = async (url: string) => {
    await api.feeds.create({ title: new URL(url).hostname, url });
    setShowAddFeed(false);
    loadData();
  };

  const deleteFeed = async (id: string) => { await api.feeds.delete(id); loadData(); };

  const fetchFeed = async (id: string) => { await api.feeds.fetch(id); loadData(); };

  const addRepo = async (fullName: string) => {
    const [owner, repo] = fullName.split('/');
    if (!owner || !repo) return;
    await api.github.addRepo({ owner, repo, auto_create_tasks: true });
    setShowAddRepo(false);
    loadData();
  };

  const removeRepo = async (id: string) => { await api.github.removeRepo(id); loadData(); };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-mc-bg dark:bg-gray-950 flex items-center justify-center">
        <Loader2 size={24} className="text-mc-accent animate-spin" />
      </div>
    );
  }

  const toggleNotifPref = async (key: keyof api.NotificationPrefs) => {
    if (!notifPrefs) return;
    const updated = { ...notifPrefs, [key]: !notifPrefs[key] };
    setNotifPrefs(updated);
    try { await api.updateNotificationPrefs({ [key]: updated[key] }); } catch {
      setNotifPrefs(notifPrefs); // rollback
    }
  };

  const tabs = [
    { key: 'general', label: 'General', icon: Settings },
    { key: 'notifications', label: 'Notifications', icon: Bell },
    { key: 'api-keys', label: 'API Keys', icon: Key },
    { key: 'github', label: 'GitHub', icon: Globe },
    { key: 'feeds', label: 'RSS Feeds', icon: Rss },
  ] as const;

  return (
    <div className="min-h-screen bg-mc-bg dark:bg-gray-950 transition-colors">
      <header className="px-4 sm:px-6 lg:px-8 py-3 bg-white dark:bg-gray-900 border-b border-mc-border dark:border-gray-800 sticky top-0 z-30">
        <div className="max-w-[1600px] mx-auto flex items-center gap-3">
          <Settings size={18} className="text-mc-accent" />
          <h1 className="text-base font-bold text-mc-text dark:text-gray-100">Settings</h1>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Tabs */}
        <div className="flex gap-1 mb-6 border-b border-mc-border dark:border-gray-800 pb-0">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={clsx(
                'flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-all cursor-pointer bg-transparent border-b-2 -mb-px',
                activeTab === tab.key
                  ? 'border-mc-accent text-mc-accent'
                  : 'border-transparent text-mc-muted hover:text-mc-text'
              )}
            >
              <tab.icon size={14} />
              {tab.label}
            </button>
          ))}
        </div>

        {/* General */}
        {activeTab === 'general' && health && (
          <div className="flex flex-col gap-4 max-w-2xl">
            <Card className="p-4">
              <h3 className="text-sm font-semibold text-mc-text dark:text-gray-100 mb-3">System Status</h3>
              <div className="flex flex-col gap-2.5">
                {[
                  { label: 'Database', value: health.database, ok: health.database === 'connected' },
                  { label: 'LLM Provider', value: health.llm_provider, ok: true },
                  { label: 'Telegram', value: health.telegram, ok: health.telegram !== 'not configured' },
                  { label: 'Status', value: health.status, ok: health.status === 'ok' },
                ].map((item) => (
                  <div key={item.label} className="flex items-center justify-between py-1">
                    <span className="text-sm text-mc-muted dark:text-gray-400">{item.label}</span>
                    <div className="flex items-center gap-2">
                      <span className={clsx('w-2 h-2 rounded-full', item.ok ? 'bg-emerald-500' : 'bg-amber-400')} />
                      <span className="text-sm text-mc-text dark:text-gray-200">{item.value}</span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}

        {/* Notifications */}
        {activeTab === 'notifications' && notifPrefs && (
          <div className="flex flex-col gap-4 max-w-2xl">
            <p className="text-sm text-mc-muted dark:text-gray-400">
              Control which notifications are sent to Telegram. Urgent notifications are sent immediately, routine ones are batched into a morning digest.
            </p>
            <Card className="p-4">
              <h3 className="text-sm font-semibold text-mc-text dark:text-gray-100 mb-4">Telegram Notifications</h3>
              <div className="flex flex-col gap-3">
                {([
                  { key: 'agent_completions' as const, label: 'Agent completions', desc: 'When an agent finishes a scheduled run (routine)' },
                  { key: 'agent_failures' as const, label: 'Agent failures', desc: 'When an agent run fails or errors out (urgent)' },
                  { key: 'signal_summary' as const, label: 'New leads found', desc: 'Summary count of new marketing signals discovered (urgent if high relevance)' },
                  { key: 'content_drafts' as const, label: 'Content drafts ready', desc: 'When agents create new content drafts for review (routine)' },
                ]).map((item) => (
                  <div key={item.key} className="flex items-center justify-between py-2 border-b border-mc-border/40 dark:border-gray-800/40 last:border-0">
                    <div>
                      <div className="text-sm font-medium text-mc-text dark:text-gray-200">{item.label}</div>
                      <div className="text-xs text-mc-dim mt-0.5">{item.desc}</div>
                    </div>
                    <button
                      onClick={() => toggleNotifPref(item.key)}
                      className={clsx(
                        'relative w-10 h-5 rounded-full transition-colors cursor-pointer',
                        notifPrefs[item.key] ? 'bg-mc-accent' : 'bg-gray-300 dark:bg-gray-600'
                      )}
                    >
                      <span className={clsx(
                        'absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform',
                        notifPrefs[item.key] ? 'translate-x-5' : 'translate-x-0.5'
                      )} />
                    </button>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}

        {/* API Keys */}
        {activeTab === 'api-keys' && (
          <div className="flex flex-col gap-4 max-w-2xl">
            <div className="flex items-center justify-between">
              <p className="text-sm text-mc-muted dark:text-gray-400">Manage API keys for external access to your Mission Control data.</p>
              <button
                onClick={() => setShowNewKey(true)}
                className="flex items-center gap-2 px-3 py-1.5 bg-mc-accent text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors cursor-pointer"
              >
                <Plus size={14} /> New Key
              </button>
            </div>

            {createdKey && (
              <Card className="p-4 border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950">
                <div className="flex items-center gap-2 mb-2">
                  <Shield size={14} className="text-emerald-600" />
                  <span className="text-sm font-semibold text-emerald-700 dark:text-emerald-400">API Key Created</span>
                </div>
                <p className="text-xs text-emerald-600 dark:text-emerald-400 mb-2">Copy this key now — it won't be shown again.</p>
                <div className="flex items-center gap-2">
                  <code className="text-xs bg-white dark:bg-gray-800 border border-emerald-200 dark:border-emerald-800 rounded px-2 py-1 font-mono flex-1 truncate">{createdKey}</code>
                  <button
                    onClick={() => copyToClipboard(createdKey)}
                    className="px-2 py-1 rounded-lg border border-emerald-200 dark:border-emerald-800 bg-white dark:bg-gray-800 text-emerald-600 hover:bg-emerald-50 cursor-pointer transition-colors"
                  >
                    {copiedKey ? <Check size={14} /> : <Copy size={14} />}
                  </button>
                </div>
              </Card>
            )}

            {showNewKey && (
              <Card className="p-4">
                <div className="flex gap-2">
                  <input
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') createApiKey(); if (e.key === 'Escape') setShowNewKey(false); }}
                    placeholder="Key name (e.g., Dashboard Bot)"
                    className="flex-1 border border-mc-border dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-mc-text dark:text-gray-200 bg-white dark:bg-gray-800 outline-none focus:border-mc-accent"
                    autoFocus
                  />
                  <button onClick={createApiKey} className="px-3 py-2 bg-mc-accent text-white text-sm rounded-lg hover:bg-blue-700 cursor-pointer">Create</button>
                  <button onClick={() => setShowNewKey(false)} className="px-2 py-2 border border-mc-border rounded-lg text-mc-muted hover:bg-gray-50 cursor-pointer bg-white dark:bg-gray-800 dark:border-gray-700">
                    <X size={14} />
                  </button>
                </div>
              </Card>
            )}

            {apiKeysList.map((k) => (
              <Card key={k.id} className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-mc-text dark:text-gray-200">{k.name}</span>
                      <Badge variant={k.is_active ? 'success' : 'error'}>{k.is_active ? 'Active' : 'Revoked'}</Badge>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-mc-dim">
                      <span className="font-mono">{k.key_prefix}...</span>
                      <span>Scopes: {k.scopes.join(', ')}</span>
                      {k.last_used_at && <span>Last used: {new Date(k.last_used_at).toLocaleDateString()}</span>}
                    </div>
                  </div>
                  {k.is_active && (
                    <button
                      onClick={() => revokeKey(k.id)}
                      className="text-xs text-mc-dim hover:text-red-500 cursor-pointer bg-transparent border-none transition-colors"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              </Card>
            ))}
            {apiKeysList.length === 0 && !showNewKey && <EmptyState icon={Key} message="No API keys yet" />}
          </div>
        )}

        {/* GitHub */}
        {activeTab === 'github' && (
          <div className="flex flex-col gap-4 max-w-2xl">
            <div className="flex items-center justify-between">
              <p className="text-sm text-mc-muted dark:text-gray-400">Link GitHub repositories to sync issues and PRs.</p>
              <button
                onClick={() => setShowAddRepo(true)}
                className="flex items-center gap-2 px-3 py-1.5 bg-mc-accent text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors cursor-pointer"
              >
                <Plus size={14} /> Add Repo
              </button>
            </div>

            {showAddRepo && (
              <InlineInput placeholder="owner/repo (e.g., acme/project)" onSubmit={addRepo} onCancel={() => setShowAddRepo(false)} />
            )}

            {reposList.map((r) => (
              <Card key={r.id} className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <Globe size={14} className="text-mc-muted" />
                      <span className="text-sm font-medium text-mc-text dark:text-gray-200">{r.full_name}</span>
                      <Badge variant={r.is_active ? 'success' : 'default'}>{r.is_active ? 'Active' : 'Inactive'}</Badge>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-mc-dim">
                      {r.sync_issues && <span>Issues</span>}
                      {r.sync_prs && <span>PRs</span>}
                      {r.auto_create_tasks && <span>Auto-tasks</span>}
                      {r.last_synced_at && <span>Last sync: {new Date(r.last_synced_at).toLocaleDateString()}</span>}
                    </div>
                  </div>
                  <button
                    onClick={() => removeRepo(r.id)}
                    className="text-xs text-mc-dim hover:text-red-500 cursor-pointer bg-transparent border-none transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </Card>
            ))}
            {reposList.length === 0 && !showAddRepo && <EmptyState icon={Globe} message="No GitHub repos linked" />}
          </div>
        )}

        {/* RSS Feeds */}
        {activeTab === 'feeds' && (
          <div className="flex flex-col gap-4 max-w-2xl">
            <div className="flex items-center justify-between">
              <p className="text-sm text-mc-muted dark:text-gray-400">Subscribe to RSS feeds to auto-import articles to your reading list.</p>
              <button
                onClick={() => setShowAddFeed(true)}
                className="flex items-center gap-2 px-3 py-1.5 bg-mc-accent text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors cursor-pointer"
              >
                <Plus size={14} /> Add Feed
              </button>
            </div>

            {showAddFeed && (
              <InlineInput placeholder="Feed URL (e.g., https://blog.example.com/rss)" onSubmit={addFeed} onCancel={() => setShowAddFeed(false)} />
            )}

            {feedsList.map((f) => (
              <Card key={f.id} className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Rss size={14} className="text-mc-muted shrink-0" />
                      <span className="text-sm font-medium text-mc-text dark:text-gray-200 truncate">{f.title}</span>
                      <Badge variant={f.is_active ? 'success' : 'default'}>{f.is_active ? 'Active' : 'Paused'}</Badge>
                      {f.error_count > 0 && <Badge variant="error">{f.error_count} errors</Badge>}
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-mc-dim">
                      <span className="truncate max-w-[200px]">{f.url}</span>
                      <span>Every {f.fetch_interval_minutes}m</span>
                      {f.last_fetched_at && <span>Last: {new Date(f.last_fetched_at).toLocaleDateString()}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => fetchFeed(f.id)}
                      className="text-xs text-mc-accent hover:underline cursor-pointer bg-transparent border-none"
                    >
                      Fetch
                    </button>
                    <button
                      onClick={() => deleteFeed(f.id)}
                      className="text-mc-dim hover:text-red-500 cursor-pointer bg-transparent border-none transition-colors"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              </Card>
            ))}
            {feedsList.length === 0 && !showAddFeed && <EmptyState icon={Rss} message="No RSS feeds yet" />}
          </div>
        )}
      </main>
    </div>
  );
}
