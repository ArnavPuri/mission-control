'use client';

import { useState, useEffect, useCallback } from 'react';
import * as api from '../lib/api';
import * as Tooltip from '@radix-ui/react-tooltip';
import {
  PenLine, Loader2, Calendar, Smile, Zap, Trophy, AlertTriangle,
  Heart, Plus, X, ChevronRight,
} from 'lucide-react';
import { clsx } from 'clsx';
import { Card, Badge, EmptyState } from '../components/shared';

const moodConfig: Record<string, { emoji: string; label: string; color: string }> = {
  great: { emoji: '😊', label: 'Great', color: 'text-emerald-600' },
  good: { emoji: '🙂', label: 'Good', color: 'text-blue-600' },
  okay: { emoji: '😐', label: 'Okay', color: 'text-amber-600' },
  low: { emoji: '😔', label: 'Low', color: 'text-orange-600' },
  bad: { emoji: '😢', label: 'Bad', color: 'text-red-600' },
};

export default function JournalPage() {
  const [entries, setEntries] = useState<api.JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newContent, setNewContent] = useState('');
  const [newMood, setNewMood] = useState<string>('');
  const [selectedEntry, setSelectedEntry] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const j = await api.journal.list(100);
      setEntries(j);
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const createEntry = async () => {
    if (!newContent.trim()) return;
    await api.journal.create({
      content: newContent.trim(),
      mood: newMood ? newMood as api.JournalEntry['mood'] : undefined,
    });
    setNewContent('');
    setNewMood('');
    setShowCreate(false);
    loadData();
  };

  const deleteEntry = async (id: string) => {
    await api.journal.delete(id);
    if (selectedEntry === id) setSelectedEntry(null);
    loadData();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-mc-bg dark:bg-gray-950 flex items-center justify-center">
        <Loader2 size={24} className="text-mc-accent animate-spin" />
      </div>
    );
  }

  const selected = selectedEntry ? entries.find((e) => e.id === selectedEntry) : null;

  // Group entries by date
  const grouped: Record<string, api.JournalEntry[]> = {};
  entries.forEach((e) => {
    const date = new Date(e.created_at).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
    if (!grouped[date]) grouped[date] = [];
    grouped[date].push(e);
  });

  return (
    <Tooltip.Provider delayDuration={200}>
      <div className="min-h-screen bg-mc-bg dark:bg-gray-950 transition-colors">
        <header className="px-4 sm:px-6 lg:px-8 py-3 bg-white dark:bg-gray-900 border-b border-mc-border dark:border-gray-800 sticky top-0 z-30">
          <div className="max-w-[1600px] mx-auto flex items-center justify-between">
            <div className="flex items-center gap-3">
              <PenLine size={18} className="text-mc-accent" />
              <h1 className="text-base font-bold text-mc-text dark:text-gray-100">Journal</h1>
              <span className="text-xs text-mc-dim">{entries.length} entries</span>
            </div>
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-2 px-3 py-1.5 bg-mc-accent text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors cursor-pointer"
            >
              <Plus size={14} />
              <span className="hidden sm:inline">New Entry</span>
            </button>
          </div>
        </header>

        <main className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {/* Create new entry */}
          {showCreate && (
            <Card className="p-4 mb-6">
              <div className="flex items-center gap-2 mb-3">
                <h3 className="text-sm font-semibold text-mc-text dark:text-gray-100">New Journal Entry</h3>
                <button onClick={() => setShowCreate(false)} className="ml-auto text-mc-dim hover:text-mc-text cursor-pointer bg-transparent border-none">
                  <X size={14} />
                </button>
              </div>
              <textarea
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
                placeholder="What's on your mind..."
                className="w-full border border-mc-border dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-mc-text dark:text-gray-200 bg-white dark:bg-gray-800 outline-none focus:border-mc-accent focus:ring-2 focus:ring-mc-accent/10 placeholder:text-mc-dim transition-all resize-none h-24"
                autoFocus
              />
              <div className="flex items-center gap-2 mt-3">
                <span className="text-xs text-mc-dim mr-1">Mood:</span>
                {Object.entries(moodConfig).map(([key, { emoji }]) => (
                  <button
                    key={key}
                    onClick={() => setNewMood(newMood === key ? '' : key)}
                    className={clsx(
                      'text-lg px-1 rounded transition-all cursor-pointer bg-transparent border-none',
                      newMood === key ? 'ring-2 ring-mc-accent scale-110' : 'opacity-50 hover:opacity-100'
                    )}
                  >
                    {emoji}
                  </button>
                ))}
                <button
                  onClick={createEntry}
                  disabled={!newContent.trim()}
                  className="ml-auto px-4 py-1.5 bg-mc-accent text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Save
                </button>
              </div>
            </Card>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Entry timeline */}
            <div className="lg:col-span-1 flex flex-col gap-4">
              {Object.entries(grouped).map(([date, dayEntries]) => (
                <div key={date}>
                  <div className="flex items-center gap-2 mb-2">
                    <Calendar size={12} className="text-mc-dim" />
                    <span className="text-xs font-semibold text-mc-dim uppercase tracking-wide">{date}</span>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    {dayEntries.map((e) => {
                      const isSelected = selectedEntry === e.id;
                      const mood = e.mood ? moodConfig[e.mood] : null;
                      return (
                        <button
                          key={e.id}
                          onClick={() => setSelectedEntry(isSelected ? null : e.id)}
                          className={clsx(
                            'w-full text-left p-3 rounded-lg border transition-all cursor-pointer bg-white dark:bg-gray-900',
                            isSelected
                              ? 'border-mc-accent shadow-md ring-2 ring-mc-accent/10'
                              : 'border-mc-border dark:border-gray-800 hover:shadow-card-hover'
                          )}
                        >
                          <div className="flex items-center gap-2 mb-1">
                            {mood && <span className="text-sm">{mood.emoji}</span>}
                            <span className="text-xs text-mc-dim">
                              {new Date(e.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                            </span>
                            {e.tags?.length > 0 && e.tags.slice(0, 2).map((t) => <Badge key={t}>{t}</Badge>)}
                          </div>
                          <p className="text-sm text-mc-text dark:text-gray-200 line-clamp-2">{e.content}</p>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
              {entries.length === 0 && <EmptyState icon={PenLine} message="No journal entries yet" />}
            </div>

            {/* Entry detail */}
            <div className="lg:col-span-2">
              {selected ? (
                <Card className="p-6">
                  <div className="flex items-center gap-3 mb-4">
                    {selected.mood && moodConfig[selected.mood] && (
                      <span className="text-2xl">{moodConfig[selected.mood].emoji}</span>
                    )}
                    <div>
                      <div className="text-sm font-semibold text-mc-text dark:text-gray-100">
                        {new Date(selected.created_at).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
                      </div>
                      <div className="text-xs text-mc-dim">
                        {new Date(selected.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                        {selected.mood && ` · ${moodConfig[selected.mood]?.label}`}
                        {selected.energy && ` · Energy: ${selected.energy}/5`}
                      </div>
                    </div>
                    <button
                      onClick={() => deleteEntry(selected.id)}
                      className="ml-auto text-mc-dim hover:text-red-500 transition-colors cursor-pointer bg-transparent border-none text-xs"
                    >
                      Delete
                    </button>
                  </div>

                  <div className="text-sm text-mc-text dark:text-gray-200 leading-relaxed whitespace-pre-wrap mb-4">
                    {selected.content}
                  </div>

                  {selected.wins?.length > 0 && (
                    <div className="mb-3">
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <Trophy size={13} className="text-emerald-500" />
                        <span className="text-xs font-semibold text-mc-dim uppercase">Wins</span>
                      </div>
                      {selected.wins.map((w, i) => (
                        <div key={i} className="flex items-center gap-2 py-1 text-sm text-emerald-700 dark:text-emerald-400">
                          <ChevronRight size={11} /> {w}
                        </div>
                      ))}
                    </div>
                  )}

                  {selected.challenges?.length > 0 && (
                    <div className="mb-3">
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <AlertTriangle size={13} className="text-amber-500" />
                        <span className="text-xs font-semibold text-mc-dim uppercase">Challenges</span>
                      </div>
                      {selected.challenges.map((c, i) => (
                        <div key={i} className="flex items-center gap-2 py-1 text-sm text-amber-700 dark:text-amber-400">
                          <ChevronRight size={11} /> {c}
                        </div>
                      ))}
                    </div>
                  )}

                  {selected.gratitude?.length > 0 && (
                    <div className="mb-3">
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <Heart size={13} className="text-pink-500" />
                        <span className="text-xs font-semibold text-mc-dim uppercase">Gratitude</span>
                      </div>
                      {selected.gratitude.map((g, i) => (
                        <div key={i} className="flex items-center gap-2 py-1 text-sm text-pink-700 dark:text-pink-400">
                          <ChevronRight size={11} /> {g}
                        </div>
                      ))}
                    </div>
                  )}

                  {selected.tags?.length > 0 && (
                    <div className="flex gap-1.5 mt-4 pt-3 border-t border-mc-border dark:border-gray-800">
                      {selected.tags.map((t) => <Badge key={t}>{t}</Badge>)}
                    </div>
                  )}
                </Card>
              ) : (
                <div className="flex items-center justify-center h-64">
                  <EmptyState icon={PenLine} message="Select an entry to read it" />
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </Tooltip.Provider>
  );
}
