import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DueBadge, dueInfo, endOfDay, formatDay, reminderPending } from '../app/components/schedule';
import { TaskDialog } from '../app/components/task-dialog';
import * as api from '../app/lib/api';

// Saturday afternoon, local time
const NOW = new Date(2026, 9, 10, 14, 30);

describe('due dates', () => {
  it('names nearby days and dates further out', () => {
    expect(formatDay(new Date(2026, 9, 10, 9), NOW)).toBe('Today');
    expect(formatDay(new Date(2026, 9, 11), NOW)).toBe('Tomorrow');
    expect(formatDay(new Date(2026, 9, 9), NOW)).toBe('Yesterday');
    expect(formatDay(new Date(2026, 9, 13), NOW)).toMatch(/Tue/);
    expect(formatDay(new Date(2026, 9, 30), NOW)).toMatch(/30/);
  });

  it('is overdue once the day is over, not during it', () => {
    expect(dueInfo(endOfDay(NOW).toISOString(), NOW).tone).toBe('today');
    expect(dueInfo(endOfDay(new Date(2026, 9, 9)).toISOString(), NOW).tone).toBe('overdue');
    expect(dueInfo(endOfDay(new Date(2026, 9, 11)).toISOString(), NOW).tone).toBe('soon');
    expect(dueInfo(endOfDay(new Date(2026, 9, 20)).toISOString(), NOW).tone).toBe('later');
  });

  it('knows whether a reminder is still to be sent', () => {
    expect(reminderPending({ remind_at: '2026-10-11T09:00:00Z', reminded_at: null })).toBe(true);
    expect(reminderPending({ remind_at: '2026-10-11T09:00:00Z', reminded_at: '2026-10-11T09:00:30Z' })).toBe(false);
    // Snoozed after it was sent
    expect(reminderPending({ remind_at: '2026-10-11T10:00:00Z', reminded_at: '2026-10-11T09:00:30Z' })).toBe(true);
  });

  it('shows nothing for a task without dates', () => {
    const task = { id: 't', text: 'x', status: 'todo', priority: 'low', source: 's', tags: [], created_at: '' } as api.Task;
    const { container } = render(<DueBadge task={task} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe('TaskDialog schedule', () => {
  beforeEach(() => vi.restoreAllMocks());

  const task: api.TaskDetail = {
    id: 't1', text: 'Send invoice', status: 'todo', priority: 'medium', source: 'telegram', tags: [],
    created_at: '2026-10-10T10:00:00Z', agent_running: false, comments: [], recurrence: 'monthly',
  };

  it('sets a due date from a quick pick', async () => {
    vi.spyOn(api.tasks, 'get').mockResolvedValue(task);
    const update = vi.spyOn(api.tasks, 'update').mockResolvedValue({ updated: true, next_id: null });
    render(<TaskDialog taskId="t1" agents={[]} projects={[]} refreshTick={0} onClose={() => {}} onChanged={() => {}} />);

    expect(await screen.findByText('Every month')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Due date'));
    fireEvent.click(await screen.findByText('Tomorrow'));

    await waitFor(() => expect(update).toHaveBeenCalled());
    const [, data] = update.mock.calls[0];
    const due = new Date(data.due_date as string);
    expect(due.getHours()).toBe(23);
    expect(due.getMinutes()).toBe(59);
  });

  it('removes a reminder', async () => {
    vi.spyOn(api.tasks, 'get').mockResolvedValue({ ...task, remind_at: '2026-10-11T09:00:00Z' });
    const update = vi.spyOn(api.tasks, 'update').mockResolvedValue({ updated: true, next_id: null });
    render(<TaskDialog taskId="t1" agents={[]} projects={[]} refreshTick={0} onClose={() => {}} onChanged={() => {}} />);

    fireEvent.click(await screen.findByLabelText('Reminder'));
    fireEvent.click(await screen.findByText('Remove reminder'));
    await waitFor(() => expect(update).toHaveBeenCalledWith('t1', { remind_at: null }));
  });
});
