'use client';

import { useEffect, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Loader2, X } from 'lucide-react';
import * as api from '../lib/api';

const STATUSES: api.Project['status'][] = ['active', 'planning', 'launched', 'paused', 'archived'];

const inputClass =
  'w-full border border-mc-border dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-mc-text dark:text-gray-200 bg-white dark:bg-gray-800 outline-none focus:border-mc-accent';
const labelClass = 'block text-xs font-medium text-mc-muted dark:text-gray-400 mb-1';

/** Edit a project's details, including the GitHub repo dev tasks go to. */
export function ProjectDialog({ project, onClose, onSaved }: {
  project: api.Project | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({ name: '', description: '', status: 'active' as api.Project['status'], url: '', github_repo: '' });
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
        <Dialog.Overlay className="fixed inset-0 bg-black/30 z-40" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed left-1/2 top-[15%] -translate-x-1/2 w-[calc(100%-2rem)] max-w-md bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-800 rounded-xl shadow-dropdown z-50 p-5 space-y-3"
        >
          <div className="flex items-center justify-between">
            <Dialog.Title className="text-base font-semibold text-mc-text dark:text-gray-100">Project</Dialog.Title>
            <Dialog.Close className="text-mc-dim hover:text-mc-text cursor-pointer" aria-label="Close"><X size={16} /></Dialog.Close>
          </div>
          <div>
            <label className={labelClass} htmlFor="project-name">Name</label>
            <input id="project-name" className={inputClass} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className={labelClass} htmlFor="project-description">Description</label>
            <textarea id="project-description" rows={3} className={inputClass} value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelClass} htmlFor="project-status">Status</label>
              <select id="project-status" className={inputClass} value={form.status}
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
            <label className={labelClass} htmlFor="project-repo">GitHub repo</label>
            <input id="project-repo" className={inputClass} value={form.github_repo} placeholder="owner/repo"
              onChange={(e) => setForm({ ...form, github_repo: e.target.value })} />
            <p className="text-[11px] text-mc-dim mt-1">Dev tasks for this project become issues here for Claude Code.</p>
          </div>
          {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <Dialog.Close className="px-3 py-1.5 text-sm rounded-lg border border-mc-border dark:border-gray-700 text-mc-muted cursor-pointer">Cancel</Dialog.Close>
            <button onClick={save} disabled={saving || !form.name.trim()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-mc-accent text-white hover:bg-blue-700 disabled:opacity-50 cursor-pointer">
              {saving && <Loader2 size={13} className="animate-spin" />} Save
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
