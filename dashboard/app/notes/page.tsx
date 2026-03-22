'use client';

import { useState, useEffect } from 'react';
import * as api from '../lib/api';
import { StickyNote, Pin, Plus, Trash2, Search } from 'lucide-react';

export default function NotesPage() {
  const [notes, setNotes] = useState<api.Note[]>([]);
  const [selected, setSelected] = useState<api.Note | null>(null);
  const [searchQ, setSearchQ] = useState('');
  const [showNew, setShowNew] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newContent, setNewContent] = useState('');
  const [newTags, setNewTags] = useState('');

  useEffect(() => {
    api.notes.list().then(setNotes);
  }, []);

  const filtered = notes.filter((n) => {
    if (!searchQ) return true;
    const q = searchQ.toLowerCase();
    return n.title.toLowerCase().includes(q) || n.content.toLowerCase().includes(q) || (n.tags || []).some((t) => t.includes(q));
  });

  const pinned = filtered.filter((n) => n.is_pinned);
  const unpinned = filtered.filter((n) => !n.is_pinned);

  async function createNote() {
    if (!newTitle.trim()) return;
    await api.notes.create({
      title: newTitle,
      content: newContent,
      tags: newTags ? newTags.split(',').map((t) => t.trim()) : [],
    });
    setNewTitle('');
    setNewContent('');
    setNewTags('');
    setShowNew(false);
    api.notes.list().then(setNotes);
  }

  async function togglePin(note: api.Note) {
    await api.notes.update(note.id, { is_pinned: !note.is_pinned });
    api.notes.list().then(setNotes);
  }

  async function deleteNote(id: string) {
    await api.notes.delete(id);
    if (selected?.id === id) setSelected(null);
    api.notes.list().then(setNotes);
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <StickyNote size={20} className="text-mc-accent" />
          <h1 className="text-lg font-semibold text-mc-text dark:text-gray-100">Notes</h1>
          <span className="text-xs text-mc-dim bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded-full">{notes.length}</span>
        </div>
        <button
          onClick={() => setShowNew(!showNew)}
          className="flex items-center gap-1.5 text-xs bg-mc-accent text-white px-3 py-1.5 rounded-lg hover:bg-mc-accent-hover transition-colors cursor-pointer border-none"
        >
          <Plus size={14} /> New Note
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-mc-dim" />
        <input
          type="text"
          placeholder="Search notes..."
          value={searchQ}
          onChange={(e) => setSearchQ(e.target.value)}
          className="w-full pl-9 pr-4 py-2 text-sm border border-mc-border dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-mc-text dark:text-gray-100"
        />
      </div>

      {/* New note form */}
      {showNew && (
        <div className="bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-700 rounded-xl p-4 mb-4">
          <input
            type="text"
            placeholder="Note title..."
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            className="w-full text-sm font-medium mb-2 px-3 py-2 border border-mc-border dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-mc-text dark:text-gray-100"
            autoFocus
          />
          <textarea
            placeholder="Write your note in markdown..."
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            rows={6}
            className="w-full text-sm mb-2 px-3 py-2 border border-mc-border dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-mc-text dark:text-gray-100 font-mono resize-y"
          />
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Tags (comma-separated)"
              value={newTags}
              onChange={(e) => setNewTags(e.target.value)}
              className="flex-1 text-xs px-3 py-1.5 border border-mc-border dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-mc-text dark:text-gray-100"
            />
            <button onClick={createNote} className="text-xs bg-mc-accent text-white px-4 py-1.5 rounded-lg hover:bg-mc-accent-hover cursor-pointer border-none">
              Save
            </button>
          </div>
        </div>
      )}

      {/* Notes grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {[...pinned, ...unpinned].map((note) => (
          <div
            key={note.id}
            className="bg-white dark:bg-gray-900 border border-mc-border dark:border-gray-700 rounded-xl p-4 hover:shadow-sm transition-shadow cursor-pointer"
            onClick={() => setSelected(selected?.id === note.id ? null : note)}
          >
            <div className="flex items-start justify-between mb-2">
              <h3 className="text-sm font-medium text-mc-text dark:text-gray-100 line-clamp-1">{note.title}</h3>
              <div className="flex items-center gap-1">
                <button
                  onClick={(e) => { e.stopPropagation(); togglePin(note); }}
                  className={`p-1 rounded cursor-pointer border-none bg-transparent ${note.is_pinned ? 'text-mc-accent' : 'text-mc-dim hover:text-mc-text'}`}
                >
                  <Pin size={12} />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); deleteNote(note.id); }}
                  className="p-1 rounded text-mc-dim hover:text-mc-red cursor-pointer border-none bg-transparent"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
            <p className="text-xs text-mc-secondary dark:text-gray-400 line-clamp-3 mb-2">{note.content.slice(0, 150)}</p>
            {(note.tags || []).length > 0 && (
              <div className="flex flex-wrap gap-1">
                {note.tags.slice(0, 3).map((t) => (
                  <span key={t} className="text-[10px] bg-gray-100 dark:bg-gray-800 text-mc-dim px-1.5 py-0.5 rounded">{t}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Selected note detail */}
      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={() => setSelected(null)}>
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-mc-border dark:border-gray-800 shadow-xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-mc-text dark:text-gray-100 mb-4">{selected.title}</h2>
            <pre className="text-sm text-mc-secondary dark:text-gray-300 whitespace-pre-wrap font-mono">{selected.content}</pre>
            {(selected.tags || []).length > 0 && (
              <div className="flex flex-wrap gap-1 mt-4">
                {selected.tags.map((t) => (
                  <span key={t} className="text-xs bg-gray-100 dark:bg-gray-800 text-mc-dim px-2 py-0.5 rounded">{t}</span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
