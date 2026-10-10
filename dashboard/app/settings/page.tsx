'use client';

import { useCallback, useEffect, useState } from 'react';
import { clsx } from 'clsx';
import { Check } from 'lucide-react';
import * as api from '../lib/api';
import { useWorkspace } from '../components/workspace';
import { Button, Card, PageHeader, Spinner, inputClass, textareaClass } from '../components/shared';

const DEFAULT_PREFS: api.NotificationPrefs = {
  agent_completions: true, agent_failures: true, signal_summary: true, content_drafts: true,
};

/** Label + help on the left, control on the right (stacks on mobile). */
function Field({ label, help, children }: { label: string; help?: string; children: React.ReactNode }) {
  return (
    <div className="grid sm:grid-cols-[220px_1fr] gap-2 sm:gap-6 py-4 border-b border-mc-line last:border-0">
      <div>
        <div className="text-sm font-medium text-mc-text">{label}</div>
        {help && <div className="text-xs text-mc-muted mt-0.5">{help}</div>}
      </div>
      <div>{children}</div>
    </div>
  );
}

function Toggle({ on, onChange, label }: { on: boolean; onChange: () => void; label: string }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={onChange}
      className={clsx('relative w-9 h-5 rounded-full transition-colors cursor-pointer', on ? 'bg-mc-accent' : 'bg-mc-line-strong')}
    >
      <span className={clsx('absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform', on && 'translate-x-4')} />
    </button>
  );
}

export default function SettingsPage() {
  const { health } = useWorkspace();
  const [brand, setBrand] = useState<api.BrandProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  const load = useCallback(async () => {
    try { setBrand(await api.brand.get()); } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    if (!brand) return;
    setSaving(true);
    try {
      await api.brand.update(brand);
      setSavedAt(Date.now());
    } finally {
      setSaving(false);
    }
  };

  const prefs = brand?.notification_prefs || DEFAULT_PREFS;
  const togglePref = async (key: keyof api.NotificationPrefs) => {
    if (!brand) return;
    const updated = { ...prefs, [key]: !prefs[key] };
    setBrand({ ...brand, notification_prefs: updated });
    try { await api.brand.update({ notification_prefs: updated }); } catch {}
  };

  const set = (patch: Partial<api.BrandProfile>) => brand && setBrand({ ...brand, ...patch });
  const list = (v: string) => v.split(',').map((t) => t.trim()).filter(Boolean);

  const configured = (key: string) => (health as Record<string, string> | null)?.[key] === 'configured';
  const connections = [
    { name: 'Claude subscription', ok: configured('llm'), env: 'CLAUDE_CODE_OAUTH_TOKEN', what: 'Runs agents and the Telegram chat' },
    { name: 'Telegram bot', ok: configured('telegram'), env: 'TELEGRAM_BOT_TOKEN', what: 'Your main interface, plus briefings and alerts' },
    { name: 'GitHub', ok: configured('github'), env: 'GITHUB_TOKEN', what: 'Optional — /dev hands coding work to Claude Code' },
    { name: 'X', ok: !!health?.publishing?.x, env: 'X_API_KEY', what: 'Optional — publish drafts to X with one tap' },
    { name: 'LinkedIn', ok: !!health?.publishing?.linkedin, env: 'LINKEDIN_ACCESS_TOKEN', what: 'Optional — publish drafts to LinkedIn with one tap' },
  ];

  return (
    <>
      <PageHeader title="Settings" subtitle="Connections, your brand profile, and what Telegram tells you about" />
      {loading ? (
        <div className="py-24 flex justify-center"><Spinner size={20} /></div>
      ) : (
        <main className="max-w-3xl mx-auto px-4 sm:px-8 py-8 space-y-10 animate-fade-up">
          <section>
            <h2 className="text-sm font-semibold text-mc-text">Connections</h2>
            <p className="text-xs text-mc-muted mt-0.5 mb-3">Set in <code className="font-mono">.env</code> on the server; restart after changing.</p>
            <Card className="divide-y divide-mc-line">
              {connections.map(({ ok, ...c }) => {
                return (
                  <div key={c.name} className="flex items-center gap-3 px-4 py-3">
                    <span className={clsx('w-2 h-2 rounded-full flex-shrink-0', health == null ? 'bg-mc-line-strong' : ok ? 'bg-emerald-500' : 'bg-amber-400')} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-mc-text">{c.name}</div>
                      <div className="text-xs text-mc-muted">{c.what}</div>
                    </div>
                    <span className={clsx('text-xs', ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-mc-muted')}>
                      {health == null ? 'API unreachable' : ok ? 'Connected' : <>Set <code className="font-mono">{c.env}</code></>}
                    </span>
                  </div>
                );
              })}
            </Card>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-mc-text">Brand profile</h2>
            <p className="text-xs text-mc-muted mt-0.5 mb-3">Marketing agents write in this voice.</p>
            <Card className="px-5">
              <Field label="Name" help="You or your brand">
                <input className={inputClass} value={brand?.name || ''} placeholder="Your name or brand name" onChange={(e) => set({ name: e.target.value })} />
              </Field>
              <Field label="Bio" help="Who you are, in a few lines">
                <textarea rows={3} className={textareaClass} value={brand?.bio || ''} placeholder="Short bio for content generation" onChange={(e) => set({ bio: e.target.value })} />
              </Field>
              <Field label="Tone" help="How posts should sound">
                <input className={inputClass} value={brand?.tone || ''} placeholder="Direct, technical, a little dry" onChange={(e) => set({ tone: e.target.value })} />
              </Field>
              <Field label="Topics" help="Comma-separated">
                <input className={inputClass} value={(brand?.topics || []).join(', ')} placeholder="AI, startups, product" onChange={(e) => set({ topics: list(e.target.value) })} />
              </Field>
              <Field label="Avoid" help="Comma-separated">
                <input className={inputClass} value={(brand?.avoid || []).join(', ')} placeholder="Politics, hype words" onChange={(e) => set({ avoid: list(e.target.value) })} />
              </Field>
              <div className="flex items-center justify-end gap-3 py-4">
                {savedAt && !saving && <span className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400"><Check size={13} /> Saved</span>}
                <Button variant="primary" loading={saving} onClick={save}>Save profile</Button>
              </div>
            </Card>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-mc-text">Telegram notifications</h2>
            <p className="text-xs text-mc-muted mt-0.5 mb-3">Failures and approvals always arrive right away; the rest go into the 8:00 briefing.</p>
            <Card className="divide-y divide-mc-line">
              {([
                { key: 'agent_completions' as const, label: 'Agent completions', desc: 'When a scheduled agent finishes a run' },
                { key: 'agent_failures' as const, label: 'Agent failures', desc: 'When an agent run fails' },
                { key: 'signal_summary' as const, label: 'New leads', desc: 'When marketing agents find leads' },
                { key: 'content_drafts' as const, label: 'Content drafts', desc: 'When agents write drafts for you to review' },
              ]).map((item) => (
                <div key={item.key} className="flex items-center gap-4 px-4 py-3">
                  <div className="flex-1">
                    <div className="text-sm text-mc-text">{item.label}</div>
                    <div className="text-xs text-mc-muted">{item.desc}</div>
                  </div>
                  <Toggle on={prefs[item.key] !== false} onChange={() => togglePref(item.key)} label={item.label} />
                </div>
              ))}
            </Card>
          </section>
        </main>
      )}
    </>
  );
}
