'use client';

import { useState } from 'react';
import * as Popover from '@radix-ui/react-popover';
import { Bell, CalendarDays, ChevronDown, Repeat } from 'lucide-react';
import { clsx } from 'clsx';
import type * as api from '../lib/api';

// Due dates are days: stored as 23:59 local time, so a task is overdue once its day is over.
// Reminders are moments: "remind me at 9:00".

const DAY_MS = 86_400_000;

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

export function endOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 59);
}

function addDays(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n, d.getHours(), d.getMinutes());
}

function daysFrom(now: Date, d: Date): number {
  return Math.round((startOfDay(d).getTime() - startOfDay(now).getTime()) / DAY_MS);
}

/** "Today", "Tomorrow", "Yesterday", "Fri", "Oct 12", "Oct 12, 2027". */
export function formatDay(d: Date, now = new Date()): string {
  const days = daysFrom(now, d);
  if (days === 0) return 'Today';
  if (days === 1) return 'Tomorrow';
  if (days === -1) return 'Yesterday';
  if (days > 1 && days < 7) return d.toLocaleDateString(undefined, { weekday: 'short' });
  return d.toLocaleDateString(undefined, {
    month: 'short', day: 'numeric', ...(d.getFullYear() !== now.getFullYear() ? { year: 'numeric' } : {}),
  });
}

/** "Today 9:00", "Fri 18:30". */
export function formatWhen(iso: string, now = new Date()): string {
  const d = new Date(iso);
  const time = d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  return `${formatDay(d, now)} ${time}`;
}

export type DueTone = 'overdue' | 'today' | 'soon' | 'later';

export function dueInfo(iso: string, now = new Date()): { label: string; tone: DueTone } {
  const d = new Date(iso);
  const days = daysFrom(now, d);
  const tone: DueTone = d < now ? 'overdue' : days === 0 ? 'today' : days <= 2 ? 'soon' : 'later';
  return { label: formatDay(d, now), tone };
}

/** A pending reminder: set and not sent since it was last set. */
export function reminderPending(task: Pick<api.Task, 'remind_at' | 'reminded_at'>): boolean {
  if (!task.remind_at) return false;
  return !task.reminded_at || new Date(task.reminded_at) < new Date(task.remind_at);
}

const toneClass: Record<DueTone, string> = {
  overdue: 'text-red-600 dark:text-red-400',
  today: 'text-amber-600 dark:text-amber-400',
  soon: 'text-mc-secondary',
  later: 'text-mc-muted',
};

/** Compact due / reminder / repeat indicators for task rows and cards. */
export function DueBadge({ task, className }: { task: api.Task; className?: string }) {
  const done = task.status === 'done';
  const due = task.due_date ? dueInfo(task.due_date) : null;
  const remind = reminderPending(task) && !done ? task.remind_at! : null;
  if (!due && !remind && !task.recurrence) return null;
  return (
    <span className={clsx('inline-flex items-center gap-2 text-2xs', className)}>
      {due && (
        <span className={clsx('inline-flex items-center gap-1', done ? 'text-mc-dim' : toneClass[due.tone])} title={`Due ${due.label}`}>
          <CalendarDays size={11} /> {due.label}
        </span>
      )}
      {remind && (
        <span className="inline-flex items-center gap-1 text-mc-muted" title={`Reminder ${formatWhen(remind)}`}>
          <Bell size={11} /> {!due ? formatWhen(remind) : ''}
        </span>
      )}
      {task.recurrence && (
        <span className="inline-flex items-center gap-1 text-mc-muted" title={`Repeats ${task.recurrence}`}>
          <Repeat size={11} />
        </span>
      )}
    </span>
  );
}

// ─── Pickers ─────────────────────────────────────────────

const pad = (n: number) => String(n).padStart(2, '0');
const dateInput = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const dateTimeInput = (d: Date) => `${dateInput(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}`;

function nextWeekday(now: Date, weekday: number): Date {
  const ahead = (weekday - now.getDay() + 7) % 7 || 7;
  return addDays(now, ahead);
}

function atHour(d: Date, hour: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate(), hour, 0);
}

const triggerClass = 'max-w-full h-7 inline-flex items-center gap-1.5 px-2 -mx-2 rounded-md text-sm text-mc-text hover:bg-mc-hover cursor-pointer';
const panelClass = 'w-60 bg-mc-panel rounded-lg shadow-dropdown p-1 z-[60] animate-fade-up';
const optionClass = 'w-full flex items-center justify-between h-8 px-2 rounded-md text-sm text-mc-secondary hover:bg-mc-hover hover:text-mc-text cursor-pointer';
const fieldClass = 'w-full h-8 px-2 rounded-md bg-mc-subtle text-sm text-mc-text border border-mc-line focus:outline-none focus:ring-2 focus:ring-mc-accent/30';

function PickerShell({ label, icon: Icon, value, tone, children }: {
  label: string;
  icon: typeof Bell;
  value: string | null;
  tone?: DueTone;
  children: (close: () => void) => React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button className={triggerClass} aria-label={label}>
          <Icon size={13} className={clsx('flex-shrink-0', tone ? toneClass[tone] : 'text-mc-muted')} />
          {value ? <span className={clsx('truncate', tone && toneClass[tone])}>{value}</span> : <span className="text-mc-muted">None</span>}
          <ChevronDown size={12} className="text-mc-dim flex-shrink-0" />
        </button>
      </Popover.Trigger>
      {/* No portal: inside the task sheet's focus trap, so typing a date doesn't close it */}
      <Popover.Content align="start" sideOffset={4} className={panelClass}>
        {children(() => setOpen(false))}
      </Popover.Content>
    </Popover.Root>
  );
}

function Option({ label, hint, onClick }: { label: string; hint?: string; onClick: () => void }) {
  return (
    <button type="button" className={optionClass} onClick={onClick}>
      <span>{label}</span>
      {hint && <span className="text-2xs text-mc-dim">{hint}</span>}
    </button>
  );
}

/** Due date: quick picks or any day. onChange gets an ISO string (end of that day) or null. */
export function DuePicker({ value, done, onChange }: {
  value: string | null | undefined;
  done?: boolean;
  onChange: (iso: string | null) => void;
}) {
  const now = new Date();
  const info = value ? dueInfo(value, now) : null;
  const picks: [string, Date][] = [
    ['Today', now],
    ['Tomorrow', addDays(now, 1)],
    ['Next week', nextWeekday(now, 1)],
  ];
  return (
    <PickerShell label="Due date" icon={CalendarDays} value={info?.label ?? null} tone={done ? undefined : info?.tone}>
      {(close) => {
        const pick = (iso: string | null) => { onChange(iso); close(); };
        return (
          <>
            {picks.map(([label, d]) => (
              <Option key={label} label={label} hint={d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
                onClick={() => pick(endOfDay(d).toISOString())} />
            ))}
            <div className="p-1">
              <input
                type="date"
                aria-label="Pick a due date"
                className={fieldClass}
                defaultValue={value ? dateInput(new Date(value)) : ''}
                onChange={(e) => {
                  if (!e.target.value) return;
                  const [y, m, d] = e.target.value.split('-').map(Number);
                  pick(endOfDay(new Date(y, m - 1, d)).toISOString());
                }}
              />
            </div>
            {value && <Option label="Clear due date" onClick={() => pick(null)} />}
          </>
        );
      }}
    </PickerShell>
  );
}

/** Reminder: when to ping you on Telegram. onChange gets an ISO string or null. */
export function ReminderPicker({ value, sent, onChange }: {
  value: string | null | undefined;
  sent?: boolean;
  onChange: (iso: string | null) => void;
}) {
  const now = new Date();
  const [draft, setDraft] = useState('');
  const picks: [string, Date][] = [
    ['In 1 hour', new Date(now.getTime() + 3_600_000)],
    ['Tomorrow morning', atHour(addDays(now, 1), 9)],
    ['Monday morning', atHour(nextWeekday(now, 1), 9)],
  ];
  if (now.getHours() < 18) picks.splice(1, 0, ['This evening', atHour(now, 18)]);
  const label = value ? `${formatWhen(value, now)}${sent ? ' · sent' : ''}` : null;
  return (
    <PickerShell label="Reminder" icon={Bell} value={label}>
      {(close) => {
        const pick = (iso: string | null) => { onChange(iso); close(); };
        return (
          <>
            {picks.map(([text, d]) => (
              <Option key={text} label={text} hint={formatWhen(d.toISOString(), now)} onClick={() => pick(d.toISOString())} />
            ))}
            <form
              className="p-1 flex gap-1"
              onSubmit={(e) => { e.preventDefault(); if (draft) pick(new Date(draft).toISOString()); }}
            >
              <input
                type="datetime-local"
                aria-label="Pick a reminder time"
                className={fieldClass}
                defaultValue={value ? dateTimeInput(new Date(value)) : ''}
                onChange={(e) => setDraft(e.target.value)}
              />
              <button type="submit" disabled={!draft} className="h-8 px-2 rounded-md text-xs font-medium bg-mc-accent text-mc-accent-fg disabled:opacity-40 cursor-pointer">Set</button>
            </form>
            {value && <Option label="Remove reminder" onClick={() => pick(null)} />}
            <p className="px-2 pt-1 pb-1.5 text-2xs text-mc-dim">Sent to you on Telegram.</p>
          </>
        );
      }}
    </PickerShell>
  );
}
