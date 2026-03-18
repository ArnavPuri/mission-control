'use client';

import { useState, useEffect, useRef } from 'react';
import { clsx } from 'clsx';
import { Plus, X } from 'lucide-react';

// ─── Theme ───────────────────────────────────────────────

export type Theme = 'light' | 'dark';

export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setThemeState] = useState<Theme>('light');

  useEffect(() => {
    const stored = localStorage.getItem('mc-theme') as Theme | null;
    if (stored) {
      setThemeState(stored);
      document.documentElement.classList.toggle('dark', stored === 'dark');
    }
  }, []);

  const setTheme = (t: Theme) => {
    setThemeState(t);
    localStorage.setItem('mc-theme', t);
    document.documentElement.classList.toggle('dark', t === 'dark');
  };

  return [theme, setTheme];
}

// ─── Keyboard Shortcuts ──────────────────────────────────

export interface ShortcutAction {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  description: string;
  action: () => void;
}

export function useKeyboardShortcuts(shortcuts: ShortcutAction[], enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    const handler = (e: KeyboardEvent) => {
      // Don't trigger when typing in inputs
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      for (const s of shortcuts) {
        if (s.ctrl && !(e.metaKey || e.ctrlKey)) continue;
        if (s.shift && !e.shiftKey) continue;
        if (e.key.toLowerCase() === s.key.toLowerCase()) {
          e.preventDefault();
          s.action();
          return;
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [shortcuts, enabled]);
}

// ─── Shared UI Primitives ────────────────────────────────

export function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={clsx('bg-white dark:bg-gray-900 rounded-xl border border-mc-border dark:border-gray-800 shadow-card', className)}>
      {children}
    </div>
  );
}

export function Badge({ children, variant = 'default' }: {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'error' | 'purple' | 'blue';
}) {
  const styles: Record<string, string> = {
    default: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
    success: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400',
    warning: 'bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-400',
    error: 'bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-400',
    purple: 'bg-violet-50 text-violet-700 dark:bg-violet-950 dark:text-violet-400',
    blue: 'bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-400',
  };
  return (
    <span className={clsx('inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium', styles[variant])}>
      {children}
    </span>
  );
}

export function SectionHeader({ icon: Icon, title, count, onAdd, extra }: {
  icon: React.ElementType; title: string; count: number; onAdd?: () => void; extra?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-2">
        <Icon size={15} className="text-mc-muted dark:text-gray-500" />
        <h3 className="text-sm font-semibold text-mc-text dark:text-gray-100">{title}</h3>
        <span className="text-xs text-mc-dim dark:text-gray-500 font-medium">{count}</span>
      </div>
      <div className="flex items-center gap-2">
        {extra}
        {onAdd && (
          <button
            onClick={onAdd}
            className="w-7 h-7 rounded-lg border border-mc-border dark:border-gray-700 bg-white dark:bg-gray-800 text-mc-muted dark:text-gray-400 hover:bg-mc-accent-light hover:text-mc-accent dark:hover:bg-blue-950 dark:hover:text-blue-400 hover:border-mc-accent/30 transition-all flex items-center justify-center cursor-pointer"
          >
            <Plus size={14} />
          </button>
        )}
      </div>
    </div>
  );
}

export function InlineInput({ placeholder, onSubmit, onCancel }: {
  placeholder: string; onSubmit: (v: string) => void; onCancel: () => void;
}) {
  const [val, setVal] = useState('');
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { ref.current?.focus(); }, []);
  return (
    <div className="flex gap-2 mb-3">
      <input
        ref={ref} value={val} onChange={(e) => setVal(e.target.value)} placeholder={placeholder}
        onKeyDown={(e) => { if (e.key === 'Enter' && val.trim()) { onSubmit(val.trim()); setVal(''); } if (e.key === 'Escape') onCancel(); }}
        className="flex-1 border border-mc-border dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-mc-text dark:text-gray-200 bg-white dark:bg-gray-800 outline-none focus:border-mc-accent focus:ring-2 focus:ring-mc-accent/10 placeholder:text-mc-dim transition-all"
      />
      <button
        onClick={() => { if (val.trim()) { onSubmit(val.trim()); setVal(''); } }}
        className="px-3 py-2 bg-mc-accent text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors cursor-pointer"
      >
        Add
      </button>
      <button onClick={onCancel} className="px-2 py-2 bg-white dark:bg-gray-800 border border-mc-border dark:border-gray-700 text-mc-muted rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors cursor-pointer">
        <X size={14} />
      </button>
    </div>
  );
}

export function StatusIndicator({ status }: { status: string }) {
  const config: Record<string, { color: string; pulse: boolean }> = {
    running: { color: 'bg-emerald-500', pulse: true },
    active: { color: 'bg-emerald-500', pulse: true },
    idle: { color: 'bg-gray-300 dark:bg-gray-600', pulse: false },
    planning: { color: 'bg-amber-400', pulse: false },
    paused: { color: 'bg-amber-400', pulse: false },
    error: { color: 'bg-red-500', pulse: false },
    disabled: { color: 'bg-gray-200 dark:bg-gray-700', pulse: false },
    archived: { color: 'bg-gray-200 dark:bg-gray-700', pulse: false },
  };
  const c = config[status] || { color: 'bg-gray-300', pulse: false };
  return (
    <span className="relative flex h-2.5 w-2.5">
      {c.pulse && <span className={clsx('animate-ping absolute inline-flex h-full w-full rounded-full opacity-50', c.color)} />}
      <span className={clsx('relative inline-flex rounded-full h-2.5 w-2.5', c.color)} />
    </span>
  );
}

export function EmptyState({ icon: Icon, message, small = false }: { icon: React.ElementType; message: string; small?: boolean }) {
  return (
    <div className={clsx('flex flex-col items-center justify-center text-mc-dim', small ? 'py-6' : 'py-10')}>
      <Icon size={small ? 20 : 28} className="mb-2 text-gray-300 dark:text-gray-700" />
      <span className={clsx('text-mc-muted dark:text-gray-500', small ? 'text-xs' : 'text-sm')}>{message}</span>
    </div>
  );
}

export function StatCard({ label, value, accent }: { label: string; value: string | number; accent?: boolean }) {
  return (
    <div className="text-center px-3 sm:px-4">
      <div className={clsx('text-base sm:text-lg font-bold tabular-nums', accent ? 'text-mc-accent' : 'text-mc-text dark:text-gray-100')}>{value}</div>
      <div className="text-[10px] sm:text-[11px] text-mc-muted dark:text-gray-500 font-medium tracking-wide uppercase">{label}</div>
    </div>
  );
}
