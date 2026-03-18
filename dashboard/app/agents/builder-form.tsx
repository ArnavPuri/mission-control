'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Radio, Sun, Plus, Save, X, ChevronDown, Eye, EyeOff,
  Zap, Loader2, Sparkles,
} from 'lucide-react';
import { clsx } from 'clsx';
import * as api from '../lib/api';
import { Card, Badge } from '../components/shared';

// ─── Helpers ──────────────────────────────────────────────

function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

// ─── Data Access Options ─────────────────────────────────

const DATA_OPTIONS = [
  'projects', 'tasks', 'ideas', 'reading', 'habits',
  'goals', 'journal', 'marketing_signals', 'marketing_content',
] as const;

const TOOL_OPTIONS = ['web_search', 'bash', 'write'] as const;

const AGENT_TYPES = ['marketing', 'research', 'ops', 'content', 'general'] as const;

const MODELS = [
  { value: 'claude-haiku-4-5', label: 'Claude Haiku 4.5' },
  { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
] as const;

const VARIABLE_MAP: Record<string, string> = {
  projects: '{{projects}}',
  tasks: '{{tasks}}',
  ideas: '{{ideas}}',
  reading: '{{reading}}',
  habits: '{{habits}}',
  goals: '{{goals}}',
  journal: '{{journal}}',
  marketing_signals: '{{marketing_signals}}',
  marketing_content: '{{marketing_content}}',
};

const PREVIEW_MAP: Record<string, string> = {
  projects: '[3 projects]',
  tasks: '[5 tasks]',
  ideas: '[2 ideas]',
  reading: '[4 reading items]',
  habits: '[3 habits]',
  goals: '[2 goals]',
  journal: '[1 journal entry]',
  marketing_signals: '[6 signals]',
  marketing_content: '[3 content pieces]',
};

// ─── Templates ───────────────────────────────────────────

interface AgentTemplate {
  name: string;
  description: string;
  category: 'marketing' | 'productivity';
  icon: 'Radio' | 'Sun';
  defaults: Partial<api.AgentDetail>;
}

const TEMPLATES: AgentTemplate[] = [
  {
    name: 'Reddit Scout',
    description: 'Find relevant Reddit threads and discussions about your projects and niche.',
    category: 'marketing',
    icon: 'Radio',
    defaults: {
      name: 'Reddit Scout',
      agent_type: 'marketing',
      model: 'claude-sonnet-4-6',
      max_budget_usd: 0.25,
      tools: ['web_search'],
      data_reads: ['projects', 'tasks'],
      data_writes: ['marketing_signals', 'marketing_content'],
      schedule_type: 'interval',
      schedule_value: '6h',
      prompt_template: `You are a Reddit scout agent. Your job is to find relevant Reddit threads where our projects could be mentioned or where our target audience is discussing related problems.

Search for threads related to the projects in your context. For each relevant thread:
1. Assess relevance (0-1 score)
2. Identify the signal type (opportunity, feedback, competitor, trend)
3. Create a marketing signal with the thread details

Focus on threads from the last 24 hours. Prioritize high-engagement threads.`,
      config: { requires_approval: false, max_actions: 5 },
    },
  },
  {
    name: 'Daily Check-in',
    description: 'Morning review of tasks, habits, and goals with a summary and suggested focus.',
    category: 'productivity',
    icon: 'Sun',
    defaults: {
      name: 'Daily Check-in',
      agent_type: 'ops',
      model: 'claude-haiku-4-5',
      max_budget_usd: 0.10,
      tools: [],
      data_reads: ['tasks', 'habits', 'goals'],
      data_writes: [],
      schedule_type: 'cron',
      schedule_value: '0 9 * * *',
      prompt_template: `You are a daily check-in assistant. Every morning, review the current state of tasks, habits, and goals.

Produce a brief summary covering:
1. Tasks due today or overdue
2. Habit streaks at risk (not completed yesterday)
3. Goals with upcoming deadlines
4. Suggested top 3 focus items for today

Keep it concise and actionable.`,
      config: { requires_approval: false, max_actions: 5 },
    },
  },
];

// ─── Form State ──────────────────────────────────────────

interface FormState {
  name: string;
  slug: string;
  description: string;
  agent_type: string;
  prompt_template: string;
  model: string;
  max_budget_usd: number;
  timeout_seconds: number;
  data_reads: string[];
  data_writes: string[];
  tools: string[];
  schedule_type: string;
  schedule_value: string;
  requires_approval: boolean;
  max_actions: number;
  chain_to: string;
}

function defaultFormState(): FormState {
  return {
    name: '',
    slug: '',
    description: '',
    agent_type: 'general',
    prompt_template: '',
    model: 'claude-haiku-4-5',
    max_budget_usd: 0.10,
    timeout_seconds: 300,
    data_reads: [],
    data_writes: [],
    tools: [],
    schedule_type: 'manual',
    schedule_value: '',
    requires_approval: false,
    max_actions: 5,
    chain_to: '',
  };
}

function formStateFromDefaults(defaults: Partial<api.AgentDetail>): FormState {
  const config = (defaults.config || {}) as Record<string, unknown>;
  return {
    name: defaults.name || '',
    slug: slugify(defaults.name || ''),
    description: defaults.description || '',
    agent_type: defaults.agent_type || 'general',
    prompt_template: defaults.prompt_template || '',
    model: defaults.model || 'claude-haiku-4-5',
    max_budget_usd: defaults.max_budget_usd ?? 0.10,
    timeout_seconds: (config.timeout_seconds as number) ?? 300,
    data_reads: defaults.data_reads || [],
    data_writes: defaults.data_writes || [],
    tools: defaults.tools || [],
    schedule_type: defaults.schedule_type || 'manual',
    schedule_value: defaults.schedule_value || '',
    requires_approval: (config.requires_approval as boolean) ?? false,
    max_actions: (config.max_actions as number) ?? 5,
    chain_to: (config.chain_to as string) ?? '',
  };
}

// ─── Props ───────────────────────────────────────────────

export interface AgentBuilderFormProps {
  initialData?: Partial<api.AgentDetail>;
  agentId?: string;
  showTemplates?: boolean;
}

// ─── Component ───────────────────────────────────────────

export function AgentBuilderForm({
  initialData,
  agentId,
  showTemplates = true,
}: AgentBuilderFormProps) {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(
    initialData ? formStateFromDefaults(initialData) : defaultFormState(),
  );
  const [showForm, setShowForm] = useState(!showTemplates || !!initialData);
  const [slugManual, setSlugManual] = useState(false);
  const [previewPrompt, setPreviewPrompt] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aiWriting, setAiWriting] = useState(false);
  const [aiDescription, setAiDescription] = useState('');

  const isEdit = !!agentId;

  const ICON_MAP: Record<string, React.ElementType> = { Radio, Sun };

  // ── Handlers ──

  const updateField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => {
      const next = { ...prev, [key]: value };
      if (key === 'name' && !slugManual) {
        next.slug = slugify(value as string);
      }
      return next;
    });
  };

  const toggleArrayField = (key: 'data_reads' | 'data_writes' | 'tools', value: string) => {
    setForm((prev) => {
      const arr = prev[key];
      return {
        ...prev,
        [key]: arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value],
      };
    });
  };

  const applyTemplate = (template: AgentTemplate) => {
    setForm(formStateFromDefaults(template.defaults));
    setSlugManual(false);
    setShowForm(true);
  };

  const startFromScratch = () => {
    setForm(defaultFormState());
    setSlugManual(false);
    setShowForm(true);
  };

  const getPreviewedPrompt = () => {
    let text = form.prompt_template;
    for (const read of form.data_reads) {
      const variable = VARIABLE_MAP[read];
      const placeholder = PREVIEW_MAP[read] || `[${read}]`;
      if (variable) {
        text = text.replaceAll(variable, placeholder);
      }
    }
    return text;
  };

  const handleAiWrite = async () => {
    if (!aiDescription.trim()) return;
    setAiWriting(true);
    try {
      const result = await api.agents.expandPrompt({
        description: aiDescription.trim(),
        agent_type: form.agent_type,
        data_reads: form.data_reads,
        data_writes: form.data_writes,
      });
      updateField('prompt_template', result.prompt);
      setAiDescription('');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'AI prompt generation failed');
    } finally {
      setAiWriting(false);
    }
  };

  const handleSave = async () => {
    setError(null);
    if (!form.name.trim()) { setError('Name is required'); return; }
    if (!form.slug.trim()) { setError('Slug is required'); return; }
    if (!form.prompt_template.trim()) { setError('Prompt is required'); return; }

    setSaving(true);
    try {
      const payload: Partial<api.AgentDetail> = {
        name: form.name.trim(),
        slug: form.slug.trim(),
        description: form.description.trim(),
        agent_type: form.agent_type,
        prompt_template: form.prompt_template,
        model: form.model,
        max_budget_usd: form.max_budget_usd,
        tools: form.tools,
        data_reads: form.data_reads,
        data_writes: form.data_writes,
        schedule_type: form.schedule_type === 'manual' ? undefined : form.schedule_type,
        schedule_value: form.schedule_value || undefined,
        config: {
          timeout_seconds: form.timeout_seconds,
          requires_approval: form.requires_approval,
          max_actions: form.max_actions,
          ...(form.chain_to ? { chain_to: form.chain_to } : {}),
        },
      };

      if (isEdit) {
        await api.agents.update(agentId, payload);
      } else {
        await api.agents.create(payload);
      }
      router.push('/agents');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to save agent';
      setError(message);
    } finally {
      setSaving(false);
    }
  };

  // ── Render helpers ──

  const inputClass =
    'w-full border border-mc-border dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-mc-text dark:text-gray-200 bg-white dark:bg-gray-800 outline-none focus:border-mc-accent focus:ring-2 focus:ring-mc-accent/10 placeholder:text-mc-dim transition-all';

  const selectClass =
    'w-full border border-mc-border dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-mc-text dark:text-gray-200 bg-white dark:bg-gray-800 outline-none focus:border-mc-accent focus:ring-2 focus:ring-mc-accent/10 transition-all appearance-none cursor-pointer';

  const labelClass = 'block text-xs font-semibold text-mc-text dark:text-gray-300 mb-1.5';

  const sectionTitle = (title: string, number: number) => (
    <div className="flex items-center gap-2 mb-4">
      <span className="w-6 h-6 rounded-full bg-mc-accent/10 dark:bg-blue-950 text-mc-accent text-xs font-bold flex items-center justify-center">
        {number}
      </span>
      <h3 className="text-sm font-bold text-mc-text dark:text-gray-100">{title}</h3>
    </div>
  );

  const checkboxItem = (
    label: string,
    checked: boolean,
    onChange: () => void,
  ) => (
    <label
      key={label}
      className={clsx(
        'flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-medium cursor-pointer transition-all',
        checked
          ? 'bg-mc-accent/5 dark:bg-blue-950/50 border-mc-accent/30 dark:border-blue-800 text-mc-accent dark:text-blue-400'
          : 'bg-white dark:bg-gray-800 border-mc-border dark:border-gray-700 text-mc-muted dark:text-gray-400 hover:border-mc-accent/20',
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="sr-only"
      />
      <span
        className={clsx(
          'w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0 transition-colors',
          checked
            ? 'bg-mc-accent border-mc-accent text-white'
            : 'border-gray-300 dark:border-gray-600',
        )}
      >
        {checked && (
          <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
            <path d="M1 4L3.5 6.5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </span>
      {label}
    </label>
  );

  return (
    <>
      {/* Template Picker */}
      {showTemplates && !showForm && (
        <div className="mb-8">
          <h2 className="text-sm font-bold text-mc-text dark:text-gray-100 mb-4">Choose a template</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {TEMPLATES.map((t) => {
              const Icon = ICON_MAP[t.icon] || Zap;
              return (
                <button
                  key={t.name}
                  onClick={() => applyTemplate(t)}
                  className="text-left cursor-pointer"
                >
                  <Card className="p-5 hover:shadow-card-hover hover:border-mc-accent/30 dark:hover:border-blue-800 transition-all h-full">
                    <div className="flex items-center gap-2.5 mb-2">
                      <div className="w-8 h-8 rounded-lg bg-mc-accent/10 dark:bg-blue-950 flex items-center justify-center">
                        <Icon size={16} className="text-mc-accent" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-semibold text-mc-text dark:text-gray-100">{t.name}</div>
                      </div>
                    </div>
                    <p className="text-xs text-mc-muted dark:text-gray-400 mb-3">{t.description}</p>
                    <div className="flex items-center gap-1.5">
                      <Badge variant={t.category === 'marketing' ? 'purple' : 'blue'}>{t.category}</Badge>
                      <Badge>{t.defaults.model}</Badge>
                    </div>
                  </Card>
                </button>
              );
            })}
            <button
              onClick={startFromScratch}
              className="text-left cursor-pointer"
            >
              <Card className="p-5 hover:shadow-card-hover hover:border-mc-accent/30 dark:hover:border-blue-800 transition-all h-full flex flex-col items-center justify-center">
                <div className="w-8 h-8 rounded-lg bg-gray-100 dark:bg-gray-800 flex items-center justify-center mb-2">
                  <Plus size={16} className="text-mc-muted dark:text-gray-400" />
                </div>
                <div className="text-sm font-semibold text-mc-text dark:text-gray-100 mb-1">Start from Scratch</div>
                <p className="text-xs text-mc-muted dark:text-gray-400 text-center">Create a custom agent with a blank canvas.</p>
              </Card>
            </button>
          </div>
        </div>
      )}

      {/* Builder Form */}
      {showForm && (
        <div className="flex flex-col gap-6">
          {showTemplates && (
            <button
              onClick={() => setShowForm(false)}
              className="text-xs text-mc-muted dark:text-gray-400 hover:text-mc-accent transition-colors self-start cursor-pointer flex items-center gap-1"
            >
              <ChevronDown size={12} className="rotate-90" /> Back to templates
            </button>
          )}

          {/* Section 1 — Basics */}
          <Card className="p-5">
            {sectionTitle('Basics', 1)}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => updateField('name', e.target.value)}
                  placeholder="My New Agent"
                  className={inputClass}
                />
                <div className="mt-1 text-[11px] text-mc-dim font-mono">
                  slug: {form.slug || '...'}
                </div>
              </div>
              <div>
                <label className={labelClass}>Slug</label>
                <input
                  type="text"
                  value={form.slug}
                  onChange={(e) => {
                    setSlugManual(true);
                    updateField('slug', e.target.value);
                  }}
                  placeholder="my-new-agent"
                  className={inputClass}
                />
              </div>
              <div className="sm:col-span-2">
                <label className={labelClass}>Description</label>
                <textarea
                  value={form.description}
                  onChange={(e) => updateField('description', e.target.value)}
                  placeholder="What does this agent do?"
                  rows={3}
                  className={inputClass + ' resize-none'}
                />
              </div>
              <div>
                <label className={labelClass}>Agent Type</label>
                <div className="relative">
                  <select
                    value={form.agent_type}
                    onChange={(e) => updateField('agent_type', e.target.value)}
                    className={selectClass}
                  >
                    {AGENT_TYPES.map((t) => (
                      <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
                    ))}
                  </select>
                  <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-mc-dim pointer-events-none" />
                </div>
              </div>
            </div>
          </Card>

          {/* Section 2 — Prompt */}
          <Card className="p-5">
            {sectionTitle('Prompt', 2)}

            {/* AI Write */}
            <div className="mb-4 p-3 bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-950/30 dark:to-blue-950/30 border border-purple-200/50 dark:border-purple-800/30 rounded-lg">
              <div className="flex items-center gap-1.5 mb-2">
                <Sparkles size={13} className="text-purple-500" />
                <span className="text-xs font-semibold text-purple-700 dark:text-purple-300">AI Write</span>
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={aiDescription}
                  onChange={(e) => setAiDescription(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !aiWriting && handleAiWrite()}
                  placeholder="Describe what you want the agent to do..."
                  className="flex-1 border border-purple-200 dark:border-purple-800/50 rounded-lg px-3 py-1.5 text-sm text-mc-text dark:text-gray-200 bg-white dark:bg-gray-800 outline-none focus:border-purple-400 focus:ring-2 focus:ring-purple-400/10 placeholder:text-mc-dim"
                />
                <button
                  onClick={handleAiWrite}
                  disabled={aiWriting || !aiDescription.trim()}
                  className={clsx(
                    'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white rounded-lg transition-colors cursor-pointer whitespace-nowrap',
                    aiWriting || !aiDescription.trim()
                      ? 'bg-purple-400/60 cursor-not-allowed'
                      : 'bg-purple-600 hover:bg-purple-700',
                  )}
                >
                  {aiWriting ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                  {aiWriting ? 'Writing...' : 'Generate'}
                </button>
              </div>
              <p className="text-[10px] text-purple-500/70 dark:text-purple-400/50 mt-1.5">
                AI will expand your description into a full prompt template. You can edit the result.
              </p>
            </div>

            <div className="flex items-center justify-between mb-2">
              <label className={labelClass + ' mb-0'}>Prompt Template</label>
              <button
                onClick={() => setPreviewPrompt(!previewPrompt)}
                className="flex items-center gap-1 text-[11px] text-mc-muted dark:text-gray-400 hover:text-mc-accent transition-colors cursor-pointer"
              >
                {previewPrompt ? <EyeOff size={12} /> : <Eye size={12} />}
                {previewPrompt ? 'Edit' : 'Preview'}
              </button>
            </div>
            {previewPrompt ? (
              <div className="w-full border border-mc-border dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-mc-text dark:text-gray-200 bg-gray-50 dark:bg-gray-800/50 font-mono whitespace-pre-wrap min-h-[288px]">
                {getPreviewedPrompt() || <span className="text-mc-dim">No prompt to preview</span>}
              </div>
            ) : (
              <textarea
                value={form.prompt_template}
                onChange={(e) => updateField('prompt_template', e.target.value)}
                placeholder="Write the prompt for your agent..."
                rows={12}
                className={inputClass + ' font-mono resize-y min-h-[288px]'}
              />
            )}
            {form.data_reads.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                <span className="text-[11px] text-mc-dim mr-1">Available variables:</span>
                {form.data_reads.map((r) => (
                  <code
                    key={r}
                    className="text-[11px] px-1.5 py-0.5 bg-mc-accent/5 dark:bg-blue-950/50 text-mc-accent dark:text-blue-400 rounded font-mono"
                  >
                    {VARIABLE_MAP[r]}
                  </code>
                ))}
              </div>
            )}
          </Card>

          {/* Section 3 — Model & Budget */}
          <Card className="p-5">
            {sectionTitle('Model & Budget', 3)}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className={labelClass}>Model</label>
                <div className="relative">
                  <select
                    value={form.model}
                    onChange={(e) => updateField('model', e.target.value)}
                    className={selectClass}
                  >
                    {MODELS.map((m) => (
                      <option key={m.value} value={m.value}>{m.label}</option>
                    ))}
                  </select>
                  <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-mc-dim pointer-events-none" />
                </div>
              </div>
              <div>
                <label className={labelClass}>Max Budget (USD)</label>
                <input
                  type="number"
                  value={form.max_budget_usd}
                  onChange={(e) => updateField('max_budget_usd', parseFloat(e.target.value) || 0)}
                  step={0.05}
                  min={0}
                  className={inputClass + ' font-mono'}
                />
              </div>
              <div>
                <label className={labelClass}>Timeout (seconds)</label>
                <input
                  type="number"
                  value={form.timeout_seconds}
                  onChange={(e) => updateField('timeout_seconds', parseInt(e.target.value) || 300)}
                  min={30}
                  className={inputClass + ' font-mono'}
                />
              </div>
            </div>
          </Card>

          {/* Section 4 — Data Access */}
          <Card className="p-5">
            {sectionTitle('Data Access', 4)}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div>
                <label className={labelClass}>Reads from</label>
                <div className="grid grid-cols-2 gap-2">
                  {DATA_OPTIONS.map((opt) =>
                    checkboxItem(opt, form.data_reads.includes(opt), () => toggleArrayField('data_reads', opt)),
                  )}
                </div>
              </div>
              <div>
                <label className={labelClass}>Writes to</label>
                <div className="grid grid-cols-2 gap-2">
                  {DATA_OPTIONS.map((opt) =>
                    checkboxItem(opt, form.data_writes.includes(opt), () => toggleArrayField('data_writes', opt)),
                  )}
                </div>
              </div>
            </div>
          </Card>

          {/* Section 5 — Tools */}
          <Card className="p-5">
            {sectionTitle('Tools', 5)}
            <div className="flex flex-wrap gap-2">
              {TOOL_OPTIONS.map((opt) =>
                checkboxItem(opt, form.tools.includes(opt), () => toggleArrayField('tools', opt)),
              )}
            </div>
          </Card>

          {/* Section 6 — Schedule */}
          <Card className="p-5">
            {sectionTitle('Schedule', 6)}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Type</label>
                <div className="relative">
                  <select
                    value={form.schedule_type}
                    onChange={(e) => updateField('schedule_type', e.target.value)}
                    className={selectClass}
                  >
                    <option value="manual">Manual</option>
                    <option value="interval">Interval</option>
                    <option value="cron">Cron</option>
                  </select>
                  <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-mc-dim pointer-events-none" />
                </div>
              </div>
              {form.schedule_type === 'interval' && (
                <div>
                  <label className={labelClass}>Interval</label>
                  <input
                    type="text"
                    value={form.schedule_value}
                    onChange={(e) => updateField('schedule_value', e.target.value)}
                    placeholder="6h"
                    className={inputClass}
                  />
                </div>
              )}
              {form.schedule_type === 'cron' && (
                <div>
                  <label className={labelClass}>Cron Expression</label>
                  <input
                    type="text"
                    value={form.schedule_value}
                    onChange={(e) => updateField('schedule_value', e.target.value)}
                    placeholder="0 9 * * *"
                    className={inputClass + ' font-mono'}
                  />
                </div>
              )}
            </div>
          </Card>

          {/* Section 7 — Advanced */}
          <Card className="p-5">
            {sectionTitle('Advanced', 7)}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <span
                    className={clsx(
                      'relative w-9 h-5 rounded-full transition-colors',
                      form.requires_approval ? 'bg-mc-accent' : 'bg-gray-200 dark:bg-gray-700',
                    )}
                    onClick={() => updateField('requires_approval', !form.requires_approval)}
                  >
                    <span
                      className={clsx(
                        'absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform',
                        form.requires_approval && 'translate-x-4',
                      )}
                    />
                  </span>
                  <span className="text-xs font-semibold text-mc-text dark:text-gray-300">
                    Requires approval
                  </span>
                </label>
              </div>
              <div>
                <label className={labelClass}>Max actions per run</label>
                <input
                  type="number"
                  value={form.max_actions}
                  onChange={(e) => updateField('max_actions', parseInt(e.target.value) || 5)}
                  min={1}
                  className={inputClass + ' font-mono'}
                />
              </div>
              <div>
                <label className={labelClass}>Chain to</label>
                <input
                  type="text"
                  value={form.chain_to}
                  onChange={(e) => updateField('chain_to', e.target.value)}
                  placeholder="agent-slug"
                  className={inputClass}
                />
              </div>
            </div>
          </Card>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 px-4 py-3 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-xl text-sm text-red-700 dark:text-red-400">
              <X size={14} /> {error}
            </div>
          )}

          {/* Actions */}
          <div className="sticky bottom-0 bg-mc-bg/80 dark:bg-gray-950/80 backdrop-blur-sm border-t border-mc-border dark:border-gray-800 -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8 py-4">
            <div className="max-w-[1600px] mx-auto flex items-center justify-end gap-3">
              <Link
                href="/agents"
                className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-mc-muted dark:text-gray-400 bg-white dark:bg-gray-800 border border-mc-border dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <X size={14} /> Cancel
              </Link>
              <button
                onClick={handleSave}
                disabled={saving}
                className={clsx(
                  'flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors cursor-pointer',
                  saving ? 'bg-mc-accent/60' : 'bg-mc-accent hover:bg-blue-700',
                )}
              >
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                {isEdit ? 'Update Agent' : 'Save Agent'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
