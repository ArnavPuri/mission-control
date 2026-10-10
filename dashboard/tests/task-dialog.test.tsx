import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { TaskDialog } from '../app/components/task-dialog';
import * as api from '../app/lib/api';

const agents: api.Agent[] = [{
  id: 'a1', name: 'Navigator (Web Researcher)', slug: 'navigator-web-researcher', description: 'Research',
  agent_type: 'research', status: 'idle', model: 'm', recent_runs: [],
}];

const detail: api.TaskDetail = {
  id: 't1', text: 'Compare analytics pricing', status: 'blocked', priority: 'medium',
  source: 'telegram', tags: [], created_at: '2026-10-10T10:00:00Z',
  assigned_agent_id: 'a1', assigned_agent_name: 'Navigator (Web Researcher)',
  agent_running: false,
  comments: [
    { id: 'c1', author: 'user', body: 'Assigned to Navigator', run_id: null, created_at: '2026-10-10T10:00:00Z' },
    { id: 'c2', author: 'agent:navigator-web-researcher', body: 'Which region?', run_id: 'r1', created_at: '2026-10-10T10:01:00Z' },
  ],
};

describe('TaskDialog', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('shows the thread with agent names and the waiting status', async () => {
    vi.spyOn(api.tasks, 'get').mockResolvedValue(detail);
    render(<TaskDialog taskId="t1" agents={agents} projects={[]} refreshTick={0} onClose={() => {}} onChanged={() => {}} />);

    expect(await screen.findByText('Which region?')).toBeInTheDocument();
    expect(screen.getByText('waiting on you')).toBeInTheDocument();
    expect(screen.getAllByText(/Navigator \(Web Researcher\)/).length).toBeGreaterThan(0);
  });

  it('sends a reply to the agent', async () => {
    vi.spyOn(api.tasks, 'get').mockResolvedValue(detail);
    const comment = vi.spyOn(api.tasks, 'comment').mockResolvedValue({ added: true, agent: 'navigator-web-researcher' });
    const onChanged = vi.fn();
    render(<TaskDialog taskId="t1" agents={agents} projects={[]} refreshTick={0} onClose={() => {}} onChanged={onChanged} />);

    const box = await screen.findByPlaceholderText(/Reply to Navigator/);
    fireEvent.change(box, { target: { value: 'EU' } });
    fireEvent.click(screen.getByLabelText('Send'));

    await waitFor(() => expect(comment).toHaveBeenCalledWith('t1', 'EU'));
    expect(onChanged).toHaveBeenCalled();
  });
});
