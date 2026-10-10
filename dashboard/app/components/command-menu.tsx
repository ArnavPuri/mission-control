'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import * as Dialog from '@radix-ui/react-dialog';
import { clsx } from 'clsx';
import {
  ArrowRight, Bot, FileText, FolderOpen, Home, ListTodo, Plus, Search, Settings, Sparkles,
} from 'lucide-react';
import * as api from '../lib/api';
import { Avatar, Kbd, Spinner, agentDisplay } from './shared';
import { useWorkspace } from './workspace';

interface Item {
  id: string;
  group: string;
  label: string;
  hint?: string;
  icon: React.ReactNode;
  run: () => void | Promise<void>;
}

/**
 * ⌘K: jump anywhere, search, or turn what you typed into a task — optionally
 * handing it straight to an agent.
 */
export function CommandMenu({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const router = useRouter();
  const { agents, openTask, refresh } = useWorkspace();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<api.SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [busy, setBusy] = useState(false);
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) { setQuery(''); setResults([]); setActive(0); }
  }, [open]);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) { setResults([]); return; }
    setSearching(true);
    const t = setTimeout(async () => {
      try { setResults((await api.search.query(q, 'tasks,notes,projects', 8)).results); }
      catch { setResults([]); }
      finally { setSearching(false); }
    }, 200);
    return () => clearTimeout(t);
  }, [query]);

  const close = () => onOpenChange(false);
  const go = (href: string) => { close(); router.push(href); };

  const items = useMemo<Item[]>(() => {
    const q = query.trim();
    const list: Item[] = [];
    if (q) {
      list.push({
        id: 'create', group: 'Create', label: `Create task “${q}”`, icon: <Plus size={15} />,
        run: async () => {
          const t = await api.tasks.create({ text: q });
          await refresh();
          close();
          openTask(t.id);
        },
      });
      const assignable = agents
        .filter((a) => a.status !== 'disabled')
        .sort((a, b) => (a.slug.startsWith('ace') ? -1 : b.slug.startsWith('ace') ? 1 : 0))
        .slice(0, 4);
      for (const a of assignable) {
        const { name, role } = agentDisplay(a.name);
        list.push({
          id: `ask-${a.id}`, group: 'Hand off to an agent', label: `Ask ${name}`, hint: role,
          icon: <Avatar name={a.name} size={18} />,
          run: async () => {
            const t = await api.tasks.create({ text: q });
            await api.tasks.assign(t.id, a.id);
            await refresh();
            close();
            openTask(t.id);
          },
        });
      }
      for (const r of results) {
        const icon = r.type === 'note' ? <FileText size={15} /> : r.type === 'project' ? <FolderOpen size={15} /> : <ListTodo size={15} />;
        list.push({
          id: `${r.type}-${r.id}`, group: 'Results', label: r.title, hint: r.status?.replace('_', ' '), icon,
          run: () => {
            if (r.type === 'task') { close(); openTask(r.id); }
            else if (r.type === 'note') go(`/notes?id=${r.id}`);
            else if (r.type === 'project') go(`/tasks?project=${r.id}`);
          },
        });
      }
    }
    const nav: [string, string, React.ReactNode][] = [
      ['Home', '/', <Home key="h" size={15} />],
      ['Tasks', '/tasks', <ListTodo key="t" size={15} />],
      ['Agents', '/agents', <Bot key="a" size={15} />],
      ['Notes', '/notes', <FileText key="n" size={15} />],
      ['Settings', '/settings', <Settings key="s" size={15} />],
      ['New agent', '/agents/new', <Sparkles key="na" size={15} />],
    ];
    for (const [label, href, icon] of nav) {
      if (!q || label.toLowerCase().includes(q.toLowerCase())) {
        list.push({ id: `nav-${href}`, group: 'Go to', label, icon, run: () => go(href) });
      }
    }
    return list;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, results, agents]);

  useEffect(() => { setActive(0); }, [query, results.length]);

  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView?.({ block: 'nearest' });
  }, [active]);

  const runItem = async (item: Item | undefined) => {
    if (!item || busy) return;
    setBusy(true);
    try { await item.run(); } finally { setBusy(false); }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => Math.min(i + 1, items.length - 1)); }
    if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
    if (e.key === 'Enter') { e.preventDefault(); runItem(items[active]); }
  };

  let lastGroup = '';
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40 backdrop-blur-[2px] z-50" />
        <Dialog.Content
          aria-describedby={undefined}
          onKeyDown={onKeyDown}
          className="fixed left-1/2 top-[14%] -translate-x-1/2 w-[calc(100%-2rem)] max-w-xl bg-mc-panel rounded-xl shadow-dropdown z-50 overflow-hidden animate-fade-up"
        >
          <Dialog.Title className="sr-only">Command menu</Dialog.Title>
          <div className="flex items-center gap-2.5 px-4 h-12 border-b border-mc-line">
            <Search size={16} className="text-mc-dim" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Type a command, search, or describe a task…"
              className="flex-1 bg-transparent text-sm text-mc-text outline-none placeholder:text-mc-dim"
            />
            {(searching || busy) && <Spinner size={14} />}
          </div>
          <div ref={listRef} className="max-h-[min(420px,60vh)] overflow-y-auto p-1.5">
            {items.map((item, i) => {
              const header = item.group !== lastGroup ? item.group : null;
              lastGroup = item.group;
              return (
                <div key={item.id}>
                  {header && <div className="px-2.5 pt-2 pb-1 text-2xs font-medium text-mc-dim">{header}</div>}
                  <button
                    data-index={i}
                    onMouseMove={() => setActive(i)}
                    onClick={() => runItem(item)}
                    className={clsx(
                      'w-full h-9 flex items-center gap-2.5 px-2.5 rounded-lg text-left text-sm cursor-pointer',
                      i === active ? 'bg-mc-hover text-mc-text' : 'text-mc-secondary',
                    )}
                  >
                    <span className="w-5 flex items-center justify-center text-mc-muted">{item.icon}</span>
                    <span className="flex-1 truncate">{item.label}</span>
                    {item.hint && <span className="text-xs text-mc-dim truncate max-w-[40%]">{item.hint}</span>}
                    {i === active && <ArrowRight size={13} className="text-mc-dim" />}
                  </button>
                </div>
              );
            })}
          </div>
          <div className="flex items-center gap-3 px-4 h-9 border-t border-mc-line text-2xs text-mc-dim">
            <span className="flex items-center gap-1"><Kbd>↑</Kbd><Kbd>↓</Kbd> navigate</span>
            <span className="flex items-center gap-1"><Kbd>↵</Kbd> select</span>
            <span className="flex items-center gap-1"><Kbd>esc</Kbd> close</span>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
