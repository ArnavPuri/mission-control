'use client';

import { useEffect, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Check, Github, X } from 'lucide-react';
import { clsx } from 'clsx';
import * as api from '../lib/api';
import { Button, inputClass, textareaClass } from './shared';

const STATUSES: api.Project['status'][] = ['active', 'planning', 'launched', 'paused', 'archived'];
const COLORS = ['#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#f97316', '#eab308', '#22c55e', '#14b8a6', '#0ea5e9', '#71717a'];

const labelClass = 'block text-xs font-medium text-mc-muted mb-1.5';

/** Edit a project's details, including the GitHub repo dev tasks go to. */
export function ProjectDialog({ project, onClose, onSaved }: {
  project: api.Project | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    name: '', description: '', status: 'active' as api.Project['status'], url: '', github_repo: '', color: COLORS[0],
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (project) {
      setForm({
        name: project.name,
        description: project.description || '',
        status: project.status,
        url: project.url || '',
        github_repo: project.github_repo || '',
        color: project.color || COLORS[0],
      });
      setError(null);
    }
  }, [project]);

  const save = async () => {
    if (!project || !form.name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await api.projects.update(project.id, {
        name: form.name.trim(),
        description: form.description,
        status: form.status,
        color: form.color,
        url: form.url || undefined,
        github_repo: form.github_repo.trim() || null,
      });
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog.Root open={!!project} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40 backdrop-blur-[2px] z-50" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed left-1/2 top-[12%] -translate-x-1/2 w-[calc(100%-2rem)] max-w-lg bg-mc-panel rounded-xl shadow-dropdown z-50 animate-fade-up"
        >
          <div className="flex items-center justify-between px-5 h-12 border-b border-mc-line">
            <Dialog.Title className="text-sm font-semibold text-mc-text">Project settings</Dialog.Title>
            <Dialog.Close aria-label="Close" className="w-7 h-7 rounded-md flex items-center justify-center text-mc-muted hover:text-mc-text hover:bg-mc-hover cursor-pointer">
              <X size={16} />
            </Dialog.Close>
          </div>

          <div className="p-5 space-y-4">
            <div>
              <label className={labelClass} htmlFor="project-name">Name</label>
              <input id="project-name" className={inputClass} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div>
              <label className={labelClass} htmlFor="project-description">Description</label>
              <textarea id="project-description" rows={3} className={textareaClass} value={form.description}
                placeholder="What it is and who it's for — agents read this for context"
                onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={labelClass} htmlFor="project-status">Status</label>
                <select id="project-status" className={clsx(inputClass, 'capitalize')} value={form.status}
                  onChange={(e) => setForm({ ...form, status: e.target.value as api.Project['status'] })}>
                  {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className={labelClass} htmlFor="project-url">Website</label>
                <input id="project-url" className={inputClass} value={form.url} placeholder="https://"
                  onChange={(e) => setForm({ ...form, url: e.target.value })} />
              </div>
            </div>
            <div>
              <span className={labelClass}>Color</span>
              <div className="flex flex-wrap gap-2">
                {COLORS.map((c) => (
                  <button
                    key={c}
                    onClick={() => setForm({ ...form, color: c })}
                    aria-label={`Color ${c}`}
                    className="w-6 h-6 rounded-full flex items-center justify-center ring-offset-2 ring-offset-mc-panel cursor-pointer"
                    style={{ backgroundColor: c, boxShadow: form.color === c ? `0 0 0 2px ${c}` : undefined }}
                  >
                    {form.color === c && <Check size={12} className="text-white" />}
                  </button>
                ))}
              </div>
            </div>
            <div className="rounded-lg bg-mc-subtle ring-1 ring-mc-line p-3">
              <label className={clsx(labelClass, 'flex items-center gap-1.5')} htmlFor="project-repo"><Github size={13} /> GitHub repo</label>
              <input id="project-repo" className={inputClass} value={form.github_repo} placeholder="owner/repo"
                onChange={(e) => setForm({ ...form, github_repo: e.target.value })} />
              <p className="text-2xs text-mc-dim mt-1.5">Dev tasks for this project become issues here, picked up by Claude Code.</p>
            </div>
            {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
          </div>

          <div className="flex justify-end gap-2 px-5 py-3 border-t border-mc-line">
            <Dialog.Close asChild><Button variant="ghost">Cancel</Button></Dialog.Close>
            <Button variant="primary" loading={saving} disabled={!form.name.trim()} onClick={save}>Save changes</Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
