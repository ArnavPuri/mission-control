'use client';

import { Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { clsx } from 'clsx';
import { ArrowLeft, Eye, FileText, Pencil, Pin, Plus, Search, Trash2 } from 'lucide-react';
import * as api from '../lib/api';
import { useWorkspace } from '../components/workspace';
import { Markdown } from '../components/markdown';
import { Badge, Button, EmptyState, IconButton, PageHeader, Spinner, timeAgo } from '../components/shared';

function NoteEditor({ note, onChange, onDelete, onBack }: {
  note: api.Note;
  onChange: (patch: Partial<api.Note>) => void;
  onDelete: () => void;
  onBack: () => void;
}) {
  const [title, setTitle] = useState(note.title);
  const [content, setContent] = useState(note.content);
  const [tags, setTags] = useState((note.tags || []).join(', '));
  const [editing, setEditing] = useState(!note.content);
  const [saved, setSaved] = useState(true);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setTitle(note.title);
    setContent(note.content);
    setTags((note.tags || []).join(', '));
    setEditing(!note.content);
    setSaved(true);
  }, [note.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Autosave shortly after typing stops
  const schedule = (patch: Partial<api.Note>) => {
    setSaved(false);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => { onChange(patch); setSaved(true); }, 700);
  };

  return (
    <div className="flex flex-col min-h-0 h-full">
      <div className="flex items-center gap-1 h-11 px-4 border-b border-mc-line flex-shrink-0">
        <IconButton label="Back to list" icon={ArrowLeft} className="lg:hidden" onClick={onBack} />
        <span className="text-2xs text-mc-dim">
          {note.source !== 'manual' ? `From ${note.source} · ` : ''}{saved ? `Edited ${timeAgo(note.updated_at)}` : 'Saving…'}
        </span>
        <span className="flex-1" />
        <IconButton
          label={editing ? 'Preview' : 'Edit'}
          icon={editing ? Eye : Pencil}
          onClick={() => setEditing(!editing)}
        />
        <IconButton
          label={note.is_pinned ? 'Unpin' : 'Pin'}
          icon={Pin}
          className={note.is_pinned ? 'text-mc-accent' : ''}
          onClick={() => onChange({ is_pinned: !note.is_pinned })}
        />
        <IconButton label="Delete note" icon={Trash2} className="hover:text-red-500" onClick={onDelete} />
      </div>
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 sm:px-10 py-8">
          <input
            value={title}
            onChange={(e) => { setTitle(e.target.value); schedule({ title: e.target.value }); }}
            placeholder="Untitled"
            className="w-full bg-transparent text-2xl font-semibold tracking-tight text-mc-text outline-none placeholder:text-mc-dim"
          />
          <input
            value={tags}
            onChange={(e) => {
              setTags(e.target.value);
              schedule({ tags: e.target.value.split(',').map((t) => t.trim()).filter(Boolean) });
            }}
            placeholder="Add tags, comma-separated"
            className="w-full bg-transparent text-xs text-mc-muted outline-none mt-2 placeholder:text-mc-dim"
          />
          <div className="mt-6">
            {editing ? (
              <textarea
                autoFocus={!note.content}
                value={content}
                onChange={(e) => { setContent(e.target.value); schedule({ content: e.target.value }); }}
                placeholder="Write in markdown…"
                className="w-full min-h-[50vh] bg-transparent text-sm leading-relaxed text-mc-secondary outline-none resize-none font-mono"
              />
            ) : content ? (
              <div onDoubleClick={() => setEditing(true)} title="Double-click to edit">
                <Markdown className="text-[15px] text-mc-secondary">{content}</Markdown>
              </div>
            ) : (
              <button onClick={() => setEditing(true)} className="text-sm text-mc-dim hover:text-mc-muted cursor-pointer">Empty note — click to write</button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Notes() {
  const params = useSearchParams();
  const { tick } = useWorkspace();
  const [notes, setNotes] = useState<api.Note[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(params.get('id'));
  const [query, setQuery] = useState('');
  const [mobileDetail, setMobileDetail] = useState(!!params.get('id'));

  const load = useCallback(async () => {
    const list = await api.notes.list().catch(() => [] as api.Note[]);
    setNotes(list);
    return list;
  }, []);

  useEffect(() => { load(); }, [load, tick]);

  useEffect(() => {
    if (!selectedId && notes && notes.length) setSelectedId(notes[0].id);
  }, [notes, selectedId]);

  const q = query.trim().toLowerCase();
  const filtered = (notes ?? []).filter((n) =>
    !q || n.title.toLowerCase().includes(q) || n.content.toLowerCase().includes(q) || (n.tags || []).some((t) => t.toLowerCase().includes(q)));
  const pinned = filtered.filter((n) => n.is_pinned);
  const rest = filtered.filter((n) => !n.is_pinned);
  const selected = notes?.find((n) => n.id === selectedId) ?? null;

  const create = async () => {
    const { id } = await api.notes.create({ title: 'Untitled', content: '' });
    await load();
    setSelectedId(id);
    setMobileDetail(true);
  };

  const update = async (id: string, patch: Partial<api.Note>) => {
    setNotes((prev) => prev?.map((n) => (n.id === id ? { ...n, ...patch, updated_at: new Date().toISOString() } : n)) ?? null);
    await api.notes.update(id, patch);
  };

  const remove = async (note: api.Note) => {
    if (!confirm(`Delete “${note.title}”?`)) return;
    await api.notes.delete(note.id);
    setSelectedId(null);
    setMobileDetail(false);
    load();
  };

  const NoteItem = ({ n }: { n: api.Note }) => (
    <button
      onClick={() => { setSelectedId(n.id); setMobileDetail(true); }}
      className={clsx(
        'w-full text-left px-3 py-2.5 rounded-lg transition-colors cursor-pointer',
        n.id === selectedId ? 'bg-mc-panel ring-1 ring-mc-line shadow-card' : 'hover:bg-mc-hover/60',
      )}
    >
      <div className="flex items-center gap-1.5">
        {n.is_pinned && <Pin size={11} className="text-mc-accent flex-shrink-0" />}
        <span className="text-sm font-medium text-mc-text truncate flex-1">{n.title || 'Untitled'}</span>
        <span className="text-2xs text-mc-dim flex-shrink-0">{timeAgo(n.updated_at)}</span>
      </div>
      <p className="text-xs text-mc-muted line-clamp-2 mt-0.5">
        {n.content.replace(/[#*_`>|-]+/g, ' ').replace(/\s+/g, ' ').trim() || 'No content'}
      </p>
      {(n.tags || []).length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1.5">{n.tags.slice(0, 3).map((t) => <Badge key={t}>{t}</Badge>)}</div>
      )}
    </button>
  );

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)] md:h-screen">
      <PageHeader
        title="Notes"
        subtitle={notes ? `${notes.length} notes · agents save research and reviews here` : undefined}
        actions={<Button variant="primary" icon={Plus} onClick={create}>New note</Button>}
      />
      {notes === null ? (
        <div className="flex-1 flex items-center justify-center"><Spinner size={20} /></div>
      ) : notes.length === 0 ? (
        <EmptyState icon={FileText} message="No notes yet. Agents like Navigator and Atlas write their findings here.">
          <Button className="mt-4" icon={Plus} onClick={create}>Write a note</Button>
        </EmptyState>
      ) : (
        <div className="flex-1 min-h-0 grid lg:grid-cols-[320px_1fr]">
          <aside className={clsx('min-h-0 flex-col border-r border-mc-line', mobileDetail ? 'hidden lg:flex' : 'flex')}>
            <div className="p-3">
              <div className="relative">
                <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-mc-dim" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search notes"
                  className="h-8 w-full rounded-lg bg-mc-panel pl-8 pr-2.5 text-sm text-mc-text ring-1 ring-inset ring-mc-line placeholder:text-mc-dim outline-none focus:ring-2 focus:ring-mc-accent/50"
                />
              </div>
            </div>
            <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-0.5">
              {pinned.length > 0 && <div className="px-3 pt-1 pb-1 text-2xs font-semibold text-mc-dim uppercase tracking-wider">Pinned</div>}
              {pinned.map((n) => <NoteItem key={n.id} n={n} />)}
              {pinned.length > 0 && rest.length > 0 && <div className="px-3 pt-3 pb-1 text-2xs font-semibold text-mc-dim uppercase tracking-wider">All notes</div>}
              {rest.map((n) => <NoteItem key={n.id} n={n} />)}
              {filtered.length === 0 && <p className="text-xs text-mc-dim text-center py-6">No matches</p>}
            </div>
          </aside>
          <section className={clsx('min-h-0 bg-mc-panel', mobileDetail ? 'block' : 'hidden lg:block')}>
            {selected ? (
              <NoteEditor
                note={selected}
                onChange={(patch) => update(selected.id, patch)}
                onDelete={() => remove(selected)}
                onBack={() => setMobileDetail(false)}
              />
            ) : (
              <EmptyState icon={FileText} message="Select a note" />
            )}
          </section>
        </div>
      )}
    </div>
  );
}

export default function NotesPage() {
  return (
    <Suspense fallback={<div className="py-24 flex justify-center"><Spinner size={20} /></div>}>
      <Notes />
    </Suspense>
  );
}
