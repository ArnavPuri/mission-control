'use client';

import { useState, useEffect, useCallback } from 'react';
import * as api from '../lib/api';
import {
  Settings, Bell, Loader2, Save,
} from 'lucide-react';
import { clsx } from 'clsx';
import { Card } from '../components/shared';

export default function SettingsPage() {
  const [brand, setBrand] = useState<api.BrandProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const b = await api.brand.get().catch(() => null);
      setBrand(b);
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const saveBrand = async () => {
    if (!brand) return;
    setSaving(true);
    try {
      await api.brand.update(brand);
    } catch (e) {
      console.error('Failed to save brand profile:', e);
    } finally {
      setSaving(false);
    }
  };

  const toggleNotifPref = async (key: keyof api.NotificationPrefs) => {
    if (!brand) return;
    const prefs = brand.notification_prefs || { agent_completions: true, agent_failures: true, signal_summary: true, content_drafts: true };
    const updated = { ...prefs, [key]: !prefs[key] };
    setBrand({ ...brand, notification_prefs: updated });
    try { await api.brand.update({ notification_prefs: updated }); } catch {}
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-mc-bg dark:bg-gray-950 flex items-center justify-center">
        <Loader2 size={24} className="text-mc-accent animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-mc-bg dark:bg-gray-950 transition-colors">
      <header className="px-4 sm:px-6 lg:px-8 py-3 bg-white dark:bg-gray-900 border-b border-mc-border dark:border-gray-800 sticky top-0 z-30">
        <div className="max-w-[1600px] mx-auto flex items-center gap-3">
          <Settings size={18} className="text-mc-accent" />
          <h1 className="text-base font-bold text-mc-text dark:text-gray-100">Settings</h1>
        </div>
      </header>

      <main className="max-w-[800px] mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col gap-6">
        {/* Brand Profile */}
        <Card className="p-5">
          <h3 className="text-sm font-semibold text-mc-text dark:text-gray-100 mb-4">Brand Profile</h3>
          <div className="flex flex-col gap-4">
            <div>
              <label className="text-xs text-mc-muted block mb-1">Name</label>
              <input
                value={brand?.name || ''}
                onChange={(e) => setBrand({ ...brand!, name: e.target.value })}
                className="w-full border border-mc-border dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-mc-text dark:text-gray-200 bg-white dark:bg-gray-800 outline-none focus:border-mc-accent"
                placeholder="Your name or brand name"
              />
            </div>
            <div>
              <label className="text-xs text-mc-muted block mb-1">Bio</label>
              <textarea
                value={brand?.bio || ''}
                onChange={(e) => setBrand({ ...brand!, bio: e.target.value })}
                rows={3}
                className="w-full border border-mc-border dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-mc-text dark:text-gray-200 bg-white dark:bg-gray-800 outline-none focus:border-mc-accent resize-none"
                placeholder="Short bio for content generation"
              />
            </div>
            <div>
              <label className="text-xs text-mc-muted block mb-1">Tone</label>
              <input
                value={brand?.tone || ''}
                onChange={(e) => setBrand({ ...brand!, tone: e.target.value })}
                className="w-full border border-mc-border dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-mc-text dark:text-gray-200 bg-white dark:bg-gray-800 outline-none focus:border-mc-accent"
                placeholder="e.g. Professional but approachable, technical yet clear"
              />
            </div>
            <div>
              <label className="text-xs text-mc-muted block mb-1">Topics (comma-separated)</label>
              <input
                value={(brand?.topics || []).join(', ')}
                onChange={(e) => setBrand({ ...brand!, topics: e.target.value.split(',').map(t => t.trim()).filter(Boolean) })}
                className="w-full border border-mc-border dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-mc-text dark:text-gray-200 bg-white dark:bg-gray-800 outline-none focus:border-mc-accent"
                placeholder="e.g. AI, startups, product development"
              />
            </div>
            <div>
              <label className="text-xs text-mc-muted block mb-1">Avoid (comma-separated)</label>
              <input
                value={(brand?.avoid || []).join(', ')}
                onChange={(e) => setBrand({ ...brand!, avoid: e.target.value.split(',').map(t => t.trim()).filter(Boolean) })}
                className="w-full border border-mc-border dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-mc-text dark:text-gray-200 bg-white dark:bg-gray-800 outline-none focus:border-mc-accent"
                placeholder="e.g. Politics, controversial opinions"
              />
            </div>
            <button
              onClick={saveBrand}
              disabled={saving}
              className="self-end flex items-center gap-2 px-4 py-2 bg-mc-accent text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors cursor-pointer disabled:opacity-50"
            >
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              Save
            </button>
          </div>
        </Card>

        {/* Notification Preferences */}
        <Card className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <Bell size={16} className="text-mc-accent" />
            <h3 className="text-sm font-semibold text-mc-text dark:text-gray-100">Telegram Notifications</h3>
          </div>
          <div className="flex flex-col gap-3">
            {([
              { key: 'agent_completions' as const, label: 'Agent completions', desc: 'When an agent finishes a run' },
              { key: 'agent_failures' as const, label: 'Agent failures', desc: 'When an agent run fails' },
              { key: 'signal_summary' as const, label: 'New leads found', desc: 'Summary of new marketing signals' },
              { key: 'content_drafts' as const, label: 'Content drafts ready', desc: 'When agents create content drafts' },
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
                    brand?.notification_prefs?.[item.key] !== false ? 'bg-mc-accent' : 'bg-gray-300 dark:bg-gray-600'
                  )}
                >
                  <span className={clsx(
                    'absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform',
                    brand?.notification_prefs?.[item.key] !== false ? 'translate-x-5' : 'translate-x-0.5'
                  )} />
                </button>
              </div>
            ))}
          </div>
        </Card>
      </main>
    </div>
  );
}
