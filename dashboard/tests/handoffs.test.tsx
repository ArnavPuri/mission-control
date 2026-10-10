import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, fireEvent } from '@testing-library/react';
import * as api from '../app/lib/api';

// Capture the live-event listeners the dialog registers
const listeners: ((e: { type: string; data: any }) => void)[] = [];
vi.mock('../app/lib/live', () => ({
  subscribe: (l: (e: { type: string; data: any }) => void) => { listeners.push(l); return () => {}; },
}));

const { TaskDialog } = await import('../app/components/task-dialog');

const base: api.TaskDetail = {
  id: 't2', text: 'Draft a reply to the r/SaaS thread', status: 'in_progress', priority: 'medium',
  source: 'agent:pulse', tags: [], created_at: '2026-10-10T10:00:00Z',
  assigned_agent_id: 'a2', assigned_agent_name: 'Echo (Content Drafts)', agent_running: true,
  progress: ['Searching the web: r/SaaS analytics'],
  parent: { id: 't1', text: 'Lead: r/SaaS analytics thread' },
  handoffs: [],
  comments: [{ id: 'c1', author: 'agent:pulse', body: 'Draft a reply…', run_id: null, created_at: '2026-10-10T10:00:00Z' }],
};

describe('TaskDialog handoffs and progress', () => {
  beforeEach(() => { vi.restoreAllMocks(); listeners.length = 0; });

  it('links back to the task it was handed off from', async () => {
    vi.spyOn(api.tasks, 'get').mockResolvedValue(base);
    const open = vi.fn();
    render(<TaskDialog taskId="t2" agents={[]} projects={[]} refreshTick={0} onClose={() => {}} onChanged={() => {}} onOpenTask={open} />);
    fireEvent.click(await screen.findByText('Part of Lead: r/SaaS analytics thread'));
    expect(open).toHaveBeenCalledWith('t1');
  });

  it('shows live steps for this task only', async () => {
    vi.spyOn(api.tasks, 'get').mockResolvedValue(base);
    render(<TaskDialog taskId="t2" agents={[]} projects={[]} refreshTick={0} onClose={() => {}} onChanged={() => {}} />);
    expect(await screen.findByText('Searching the web: r/SaaS analytics')).toBeInTheDocument();

    act(() => listeners.forEach((l) => l({ type: 'run.progress', data: { task_id: 'other', steps: ['Elsewhere'] } })));
    act(() => listeners.forEach((l) => l({
      type: 'run.progress',
      data: { task_id: 't2', steps: ['Searching the web: r/SaaS analytics', 'Reading reddit.com/r/SaaS/comments/abc'] },
    })));
    expect(screen.getByText('Reading reddit.com/r/SaaS/comments/abc')).toBeInTheDocument();
    expect(screen.queryByText('Elsewhere')).not.toBeInTheDocument();
  });

  it('lists work handed to teammates', async () => {
    vi.spyOn(api.tasks, 'get').mockResolvedValue({
      ...base, id: 't1', parent: null, agent_running: false, progress: [],
      handoffs: [{ id: 't2', text: 'Draft a reply to the r/SaaS thread', status: 'done', assigned_agent_name: 'Echo (Content Drafts)' }],
    });
    const open = vi.fn();
    render(<TaskDialog taskId="t1" agents={[]} projects={[]} refreshTick={0} onClose={() => {}} onChanged={() => {}} onOpenTask={open} />);
    expect(await screen.findByText('Handed off')).toBeInTheDocument();
    fireEvent.click(screen.getAllByText('Draft a reply to the r/SaaS thread').at(-1)!);
    expect(open).toHaveBeenCalledWith('t2');
  });
});
