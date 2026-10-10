'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import { clsx } from 'clsx';
import {
  Bot, FileText, Home, ListTodo, Menu, Moon, Plus, Search, Settings, Settings2, Sun, X,
} from 'lucide-react';
import * as api from '../lib/api';
import { Kbd, useTheme } from './shared';
import { useWorkspace } from './workspace';

const NAV = [
  { href: '/', label: 'Home', icon: Home },
  { href: '/tasks', label: 'Tasks', icon: ListTodo },
  { href: '/agents', label: 'Agents', icon: Bot },
  { href: '/notes', label: 'Notes', icon: FileText },
  { href: '/settings', label: 'Settings', icon: Settings },
];

function isActive(pathname: string, href: string) {
  return href === '/' ? pathname === '/' : pathname.startsWith(href);
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const params = useSearchParams();
  const { tasks, projects, agents, approvals, content, health, refresh, openProject, openCommandMenu } = useWorkspace();
  const [theme, setTheme] = useTheme();
  const [addingProject, setAddingProject] = useState(false);
  const [projectName, setProjectName] = useState('');
  const projectInput = useRef<HTMLInputElement>(null);

  useEffect(() => { if (addingProject) projectInput.current?.focus(); }, [addingProject]);

  const openCount = tasks.filter((t) => t.status !== 'done').length;
  const needsYou = tasks.filter((t) => t.status === 'blocked').length + approvals.length
    + content.filter((c) => c.status === 'draft').length;
  const runningCount = agents.filter((a) => a.status === 'running').length;
  const activeProject = pathname.startsWith('/tasks') ? params.get('project') : null;

  const createProject = async () => {
    const name = projectName.trim();
    setAddingProject(false);
    setProjectName('');
    if (!name) return;
    await api.projects.create({ name, status: 'active' });
    refresh();
  };

  const counts: Record<string, React.ReactNode> = {
    '/': needsYou > 0
      ? <span title="Needs you" className="min-w-5 h-5 px-1.5 rounded-full bg-rose-500/10 text-rose-600 dark:text-rose-400 text-2xs font-semibold tabular-nums flex items-center justify-center">{needsYou}</span>
      : null,
    '/tasks': openCount > 0 ? <span className="text-2xs text-mc-dim tabular-nums">{openCount}</span> : null,
    '/agents': runningCount > 0
      ? <span className="flex items-center gap-1 text-2xs text-emerald-600 dark:text-emerald-400"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />{runningCount}</span>
      : null,
  };

  const connections = [
    { label: 'Claude', ok: health?.llm === 'configured' },
    { label: 'Telegram', ok: health?.telegram === 'configured' },
    { label: 'GitHub', ok: health?.github === 'configured' },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Workspace */}
      <div className="flex items-center gap-2.5 px-3 h-14 flex-shrink-0">
        <span className="w-7 h-7 rounded-lg bg-gradient-to-br from-mc-accent to-violet-500 text-white flex items-center justify-center text-xs font-bold shadow-sm">MC</span>
        <span className="text-sm font-semibold text-mc-text">Mission Control</span>
      </div>

      {/* Search */}
      <div className="px-2 mb-2">
        <button
          onClick={() => { openCommandMenu(); onNavigate?.(); }}
          className="w-full h-8 flex items-center gap-2 px-2.5 rounded-lg bg-mc-panel ring-1 ring-inset ring-mc-line text-mc-dim hover:text-mc-muted hover:ring-mc-line-strong transition-colors cursor-pointer"
        >
          <Search size={14} />
          <span className="text-sm flex-1 text-left">Search or jump to…</span>
          <Kbd>⌘K</Kbd>
        </button>
      </div>

      {/* Navigation */}
      <nav className="px-2 flex flex-col gap-px">
        {NAV.map((item) => {
          const active = isActive(pathname, item.href) && !(item.href === '/tasks' && activeProject);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={clsx(
                'h-8 flex items-center gap-2.5 px-2.5 rounded-lg text-sm transition-colors',
                active ? 'bg-mc-hover text-mc-text font-medium' : 'text-mc-muted hover:bg-mc-hover/60 hover:text-mc-text',
              )}
            >
              <item.icon size={15} className={active ? 'text-mc-text' : 'text-mc-dim'} />
              <span className="flex-1">{item.label}</span>
              {counts[item.href]}
            </Link>
          );
        })}
      </nav>

      {/* Projects */}
      <div className="mt-6 px-2 flex-1 min-h-0 overflow-y-auto">
        <div className="flex items-center justify-between px-2.5 mb-1 group">
          <span className="text-2xs font-semibold text-mc-dim uppercase tracking-wider">Projects</span>
          <button
            onClick={() => setAddingProject(true)}
            aria-label="Add project"
            className="w-5 h-5 rounded flex items-center justify-center text-mc-dim hover:text-mc-text hover:bg-mc-hover cursor-pointer"
          >
            <Plus size={13} />
          </button>
        </div>
        {addingProject && (
          <input
            ref={projectInput}
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') createProject(); if (e.key === 'Escape') setAddingProject(false); }}
            onBlur={createProject}
            placeholder="Project name"
            className="w-full h-7 mb-1 px-2.5 rounded-md bg-mc-panel ring-1 ring-mc-accent/50 text-sm text-mc-text outline-none"
          />
        )}
        <div className="flex flex-col gap-px">
          {projects.map((p) => (
            <div
              key={p.id}
              className={clsx(
                'group h-8 flex items-center gap-2.5 pl-2.5 pr-1 rounded-lg text-sm transition-colors',
                activeProject === p.id ? 'bg-mc-hover text-mc-text font-medium' : 'text-mc-muted hover:bg-mc-hover/60 hover:text-mc-text',
              )}
            >
              <Link href={`/tasks?project=${p.id}`} onClick={onNavigate} className="flex items-center gap-2.5 flex-1 min-w-0">
                <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: p.color || '#a1a1aa' }} />
                <span className="truncate">{p.name}</span>
              </Link>
              {p.open_task_count > 0 && <span className="text-2xs text-mc-dim tabular-nums group-hover:hidden">{p.open_task_count}</span>}
              <button
                onClick={() => openProject(p)}
                aria-label={`Edit ${p.name}`}
                className="hidden group-hover:flex w-6 h-6 rounded items-center justify-center text-mc-dim hover:text-mc-text cursor-pointer"
              >
                <Settings2 size={13} />
              </button>
            </div>
          ))}
          {projects.length === 0 && !addingProject && (
            <button onClick={() => setAddingProject(true)} className="h-8 px-2.5 text-left text-sm text-mc-dim hover:text-mc-muted cursor-pointer">
              Add your first project
            </button>
          )}
        </div>
      </div>

      {/* Footer: connections + theme */}
      <div className="px-3 py-3 border-t border-mc-line flex items-center gap-3">
        <div className="flex items-center gap-2.5 flex-1 min-w-0" title="Connections (from .env)">
          {connections.map((c) => (
            <span key={c.label} className="flex items-center gap-1 text-2xs text-mc-dim">
              <span className={clsx('w-1.5 h-1.5 rounded-full', health == null ? 'bg-mc-line-strong' : c.ok ? 'bg-emerald-500' : 'bg-amber-400')} />
              {c.label}
            </span>
          ))}
        </div>
        <button
          onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
          aria-label={theme === 'light' ? 'Dark mode' : 'Light mode'}
          className="w-7 h-7 rounded-md flex items-center justify-center text-mc-muted hover:text-mc-text hover:bg-mc-hover cursor-pointer"
        >
          {theme === 'light' ? <Moon size={14} /> : <Sun size={14} />}
        </button>
      </div>
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden md:block fixed left-0 top-0 bottom-0 w-60 bg-mc-canvas border-r border-mc-line z-30">
      <SidebarContent />
    </aside>
  );
}

/** Top bar + slide-over sidebar on small screens. */
export function MobileNav() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <div className="md:hidden sticky top-0 z-30 h-12 flex items-center gap-2 px-3 bg-mc-canvas/90 backdrop-blur border-b border-mc-line">
        <button onClick={() => setOpen(true)} aria-label="Open menu" className="w-8 h-8 rounded-md flex items-center justify-center text-mc-muted hover:bg-mc-hover cursor-pointer">
          <Menu size={18} />
        </button>
        <span className="text-sm font-semibold text-mc-text">Mission Control</span>
      </div>
      {open && (
        <div className="md:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute left-0 top-0 bottom-0 w-72 bg-mc-canvas border-r border-mc-line animate-fade-up">
            <button onClick={() => setOpen(false)} aria-label="Close menu" className="absolute right-2 top-3 w-8 h-8 rounded-md flex items-center justify-center text-mc-muted hover:bg-mc-hover cursor-pointer">
              <X size={16} />
            </button>
            <SidebarContent onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}
    </>
  );
}
