'use client';

import { forwardRef, useEffect, useRef, useState } from 'react';
import { clsx } from 'clsx';
import {
  Circle, CircleDashed, CircleCheck, CircleDot, CirclePause, Loader2, Plus, X,
} from 'lucide-react';

// ─── Theme ───────────────────────────────────────────────

export type Theme = 'light' | 'dark';

/** Light/dark theme, stored in localStorage; defaults to the OS setting. */
export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setThemeState] = useState<Theme>('light');

  useEffect(() => {
    setThemeState(document.documentElement.classList.contains('dark') ? 'dark' : 'light');
  }, []);

  const setTheme = (t: Theme) => {
    setThemeState(t);
    try { localStorage.setItem('mc-theme', t); } catch {}
    document.documentElement.classList.toggle('dark', t === 'dark');
  };

  return [theme, setTheme];
}

/** Runs before paint (inlined in <head>) so the page never flashes the wrong theme. */
export const themeInitScript = `(function(){try{var t=localStorage.getItem('mc-theme');if(t==='dark'||(!t&&window.matchMedia('(prefers-color-scheme: dark)').matches)){document.documentElement.classList.add('dark')}}catch(e){}})()`;

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

// ─── Helpers ─────────────────────────────────────────────

export function timeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return 'never';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** "Navigator (Web Researcher)" → { name: "Navigator", role: "Web Researcher" } */
export function agentDisplay(fullName: string | null | undefined): { name: string; role: string } {
  if (!fullName) return { name: 'Unknown', role: '' };
  const m = fullName.match(/^(.*?)\s*\((.*)\)\s*$/);
  return m ? { name: m[1], role: m[2] } : { name: fullName, role: '' };
}

const AVATAR_COLORS = [
  'bg-violet-500', 'bg-sky-500', 'bg-emerald-500', 'bg-amber-500',
  'bg-rose-500', 'bg-indigo-500', 'bg-teal-500', 'bg-fuchsia-500',
];

function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

// ─── Primitives ──────────────────────────────────────────

export function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={clsx('bg-mc-panel rounded-xl border border-mc-line shadow-card', className)}>
      {children}
    </div>
  );
}

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'purple' | 'blue' | 'accent';

export function Badge({ children, variant = 'default', className }: {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}) {
  const styles: Record<BadgeVariant, string> = {
    default: 'bg-mc-subtle text-mc-muted ring-mc-line',
    success: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 ring-emerald-500/20',
    warning: 'bg-amber-500/10 text-amber-700 dark:text-amber-400 ring-amber-500/20',
    error: 'bg-red-500/10 text-red-700 dark:text-red-400 ring-red-500/20',
    purple: 'bg-violet-500/10 text-violet-700 dark:text-violet-300 ring-violet-500/20',
    blue: 'bg-sky-500/10 text-sky-700 dark:text-sky-300 ring-sky-500/20',
    accent: 'bg-mc-accent/10 text-mc-accent ring-mc-accent/20',
  };
  return (
    <span className={clsx(
      'inline-flex items-center gap-1 h-5 px-1.5 rounded-md text-2xs font-medium ring-1 ring-inset whitespace-nowrap',
      styles[variant], className,
    )}>
      {children}
    </span>
  );
}

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'success';

export const Button = forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant; size?: 'sm' | 'md'; loading?: boolean; icon?: React.ElementType;
}>(function Button({ variant = 'secondary', size = 'md', loading, icon: Icon, className, children, disabled, ...props }, ref) {
  const styles: Record<ButtonVariant, string> = {
    primary: 'bg-mc-accent text-mc-accent-fg hover:bg-mc-accent-hover shadow-sm',
    secondary: 'bg-mc-panel text-mc-text ring-1 ring-inset ring-mc-line hover:bg-mc-hover shadow-card',
    ghost: 'text-mc-muted hover:text-mc-text hover:bg-mc-hover',
    danger: 'bg-mc-panel text-red-600 dark:text-red-400 ring-1 ring-inset ring-mc-line hover:bg-red-500/10',
    success: 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm',
  };
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={clsx(
        'inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap',
        size === 'sm' ? 'h-7 px-2.5 text-xs' : 'h-8 px-3 text-sm',
        styles[variant], className,
      )}
      {...props}
    >
      {loading ? <Loader2 size={size === 'sm' ? 12 : 14} className="animate-spin" /> : Icon ? <Icon size={size === 'sm' ? 13 : 14} /> : null}
      {children}
    </button>
  );
});

export function IconButton({ label, icon: Icon, className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string; icon: React.ElementType;
}) {
  return (
    <button
      aria-label={label}
      title={label}
      className={clsx(
        'inline-flex items-center justify-center w-7 h-7 rounded-md text-mc-muted hover:text-mc-text hover:bg-mc-hover transition-colors cursor-pointer disabled:opacity-40',
        className,
      )}
      {...props}
    >
      <Icon size={15} />
    </button>
  );
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex items-center h-5 min-w-5 justify-center px-1 rounded border border-mc-line bg-mc-subtle text-[10px] font-medium text-mc-muted font-sans">
      {children}
    </kbd>
  );
}

/** Colored monogram for an agent (or "You"). */
export function Avatar({ name, size = 22, className }: { name: string; size?: number; className?: string }) {
  const { name: short } = agentDisplay(name);
  const isUser = name === 'You' || name === 'user';
  const isSystem = name === 'System' || name === 'system';
  const color = isUser ? 'bg-mc-text text-mc-panel'
    : isSystem ? 'bg-mc-line-strong text-mc-muted'
      : `${AVATAR_COLORS[hashString(name) % AVATAR_COLORS.length]} text-white`;
  return (
    <span
      aria-hidden
      style={{ width: size, height: size, fontSize: Math.max(9, size * 0.45) }}
      className={clsx(
        'inline-flex items-center justify-center rounded-md font-semibold flex-shrink-0 select-none',
        color,
        className,
      )}
    >
      {isUser ? 'Y' : isSystem ? '·' : short.charAt(0).toUpperCase()}
    </span>
  );
}

export function PageHeader({ title, subtitle, actions, children }: {
  title: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode; children?: React.ReactNode;
}) {
  return (
    <header className="sticky top-0 z-20 bg-mc-canvas/80 backdrop-blur-md border-b border-mc-line">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-8 min-h-14 py-3 flex items-center gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="text-base font-semibold text-mc-text truncate">{title}</h1>
          {subtitle && <p className="text-xs text-mc-muted truncate">{subtitle}</p>}
        </div>
        {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
      </div>
      {children}
    </header>
  );
}

export function SectionHeader({ icon: Icon, title, count, onAdd, extra }: {
  icon?: React.ElementType; title: string; count?: number; onAdd?: () => void; extra?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-2 min-h-7">
      <div className="flex items-center gap-2">
        {Icon && <Icon size={14} className="text-mc-dim" />}
        <h2 className="text-xs font-semibold text-mc-muted uppercase tracking-wider">{title}</h2>
        {count !== undefined && <span className="text-xs text-mc-dim tabular-nums">{count}</span>}
      </div>
      <div className="flex items-center gap-1">
        {extra}
        {onAdd && <IconButton label={`Add ${title.toLowerCase()}`} icon={Plus} onClick={onAdd} />}
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
  const submit = () => { if (val.trim()) { onSubmit(val.trim()); setVal(''); } };
  return (
    <div className="flex items-center gap-1.5 mb-2">
      <input
        ref={ref} value={val} onChange={(e) => setVal(e.target.value)} placeholder={placeholder}
        onKeyDown={(e) => { if (e.key === 'Enter') submit(); if (e.key === 'Escape') onCancel(); }}
        className={clsx(inputClass, 'flex-1')}
      />
      <Button variant="primary" size="sm" onClick={submit}>Add</Button>
      <IconButton label="Cancel" icon={X} onClick={onCancel} />
    </div>
  );
}

export const inputClass =
  'h-8 w-full rounded-lg bg-mc-panel px-2.5 text-sm text-mc-text ring-1 ring-inset ring-mc-line placeholder:text-mc-dim outline-none focus:ring-2 focus:ring-mc-accent/50 transition-shadow';

export const textareaClass =
  'w-full rounded-lg bg-mc-panel px-2.5 py-2 text-sm text-mc-text ring-1 ring-inset ring-mc-line placeholder:text-mc-dim outline-none focus:ring-2 focus:ring-mc-accent/50 transition-shadow resize-none';

export function StatusIndicator({ status }: { status: string }) {
  const config: Record<string, { color: string; pulse: boolean }> = {
    running: { color: 'bg-emerald-500', pulse: true },
    active: { color: 'bg-emerald-500', pulse: false },
    launched: { color: 'bg-violet-500', pulse: false },
    idle: { color: 'bg-mc-line-strong', pulse: false },
    planning: { color: 'bg-amber-400', pulse: false },
    paused: { color: 'bg-amber-400', pulse: false },
    error: { color: 'bg-red-500', pulse: false },
    disabled: { color: 'bg-mc-line', pulse: false },
    archived: { color: 'bg-mc-line', pulse: false },
  };
  const c = config[status] || { color: 'bg-mc-line-strong', pulse: false };
  return (
    <span className="relative flex h-2 w-2 flex-shrink-0">
      {c.pulse && <span className={clsx('animate-ping absolute inline-flex h-full w-full rounded-full opacity-60', c.color)} />}
      <span className={clsx('relative inline-flex rounded-full h-2 w-2', c.color)} />
    </span>
  );
}

const TASK_STATUS: Record<string, { icon: React.ElementType; className: string; label: string }> = {
  todo: { icon: Circle, className: 'text-mc-dim', label: 'To do' },
  in_progress: { icon: CircleDot, className: 'text-amber-500', label: 'In progress' },
  blocked: { icon: CirclePause, className: 'text-rose-500', label: 'Waiting on you' },
  done: { icon: CircleCheck, className: 'text-mc-accent', label: 'Done' },
};

export function taskStatusLabel(status: string): string {
  return TASK_STATUS[status]?.label ?? status;
}

export function TaskStatusIcon({ status, size = 15 }: { status: string; size?: number }) {
  const s = TASK_STATUS[status] ?? { icon: CircleDashed, className: 'text-mc-dim', label: status };
  const Icon = s.icon;
  return <Icon size={size} className={clsx('flex-shrink-0', s.className)} aria-label={s.label} />;
}

/** Signal-bars style priority marker (Linear-like). */
export function PriorityIcon({ priority }: { priority: string }) {
  if (priority === 'critical') {
    return (
      <span title="Critical" className="inline-flex items-center justify-center w-4 h-4 rounded-[4px] bg-rose-500 text-white text-[10px] font-bold leading-none flex-shrink-0">!</span>
    );
  }
  const level = priority === 'high' ? 3 : priority === 'medium' ? 2 : 1;
  return (
    <span title={priority} className="inline-flex items-end gap-[2px] h-3.5 w-4 flex-shrink-0" aria-label={`${priority} priority`}>
      {[1, 2, 3].map((i) => (
        <span key={i} className={clsx('w-[3px] rounded-sm', i <= level ? 'bg-mc-muted' : 'bg-mc-line-strong')} style={{ height: `${i * 4 + 2}px` }} />
      ))}
    </span>
  );
}

export function EmptyState({ icon: Icon, message, small = false, children }: {
  icon: React.ElementType; message: string; small?: boolean; children?: React.ReactNode;
}) {
  return (
    <div className={clsx('flex flex-col items-center justify-center text-center', small ? 'py-6' : 'py-12')}>
      <span className={clsx('rounded-xl bg-mc-subtle ring-1 ring-mc-line flex items-center justify-center mb-3', small ? 'w-8 h-8' : 'w-10 h-10')}>
        <Icon size={small ? 15 : 18} className="text-mc-dim" />
      </span>
      <span className={clsx('text-mc-muted', small ? 'text-xs' : 'text-sm')}>{message}</span>
      {children}
    </div>
  );
}

export function StatCard({ label, value, accent }: { label: string; value: string | number; accent?: boolean }) {
  return (
    <div className="text-center px-3 sm:px-4">
      <div className={clsx('text-base sm:text-lg font-semibold tabular-nums', accent ? 'text-mc-accent' : 'text-mc-text')}>{value}</div>
      <div className="text-2xs text-mc-muted font-medium tracking-wide uppercase">{label}</div>
    </div>
  );
}

export function Spinner({ size = 16 }: { size?: number }) {
  return <Loader2 size={size} className="animate-spin text-mc-dim" />;
}
