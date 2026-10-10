import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DraftDialog } from '../app/components/draft-dialog';
import * as api from '../app/lib/api';

const draft: api.MarketingContent = {
  id: 'd1', title: 'Launch post', body: 'We shipped v1 today.', channel: 'x', status: 'draft', source: 'agent:echo',
  task_id: null, project_id: null, agent_id: null, posted_url: null, posted_at: null, notes: null, tags: [],
  created_at: '2026-10-10T10:00:00Z', updated_at: null,
};

describe('DraftDialog', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('publishes after a confirmation, saving edits first', async () => {
    const update = vi.spyOn(api.marketingContent, 'update').mockResolvedValue(draft);
    const publish = vi.spyOn(api.marketingContent, 'publish').mockResolvedValue({ posted_url: 'https://x.com/i/status/1' });
    const onChanged = vi.fn();
    render(<DraftDialog draft={draft} publishing={{ x: true, linkedin: false }} onClose={() => {}} onChanged={onChanged} />);

    fireEvent.change(screen.getByLabelText('Post'), { target: { value: 'We shipped v1 today!' } });
    fireEvent.click(screen.getByText('Publish to X'));
    expect(publish).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText('Yes, publish'));

    await waitFor(() => expect(publish).toHaveBeenCalledWith('d1'));
    expect(update).toHaveBeenCalledWith('d1', { title: 'Launch post', body: 'We shipped v1 today!' });
    expect(await screen.findByText('Posted on X')).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalled();
  });

  it('shows the error when publishing fails', async () => {
    vi.spyOn(api.marketingContent, 'publish').mockRejectedValue(new Error('X rate limit reached; try again later'));
    render(<DraftDialog draft={draft} publishing={{ x: true, linkedin: false }} onClose={() => {}} onChanged={() => {}} />);
    fireEvent.click(screen.getByText('Publish to X'));
    fireEvent.click(screen.getByText('Yes, publish'));
    expect(await screen.findByText('X rate limit reached; try again later')).toBeInTheDocument();
  });

  it('offers no publish button when the channel is not connected', () => {
    render(<DraftDialog draft={{ ...draft, channel: 'linkedin' }} publishing={{ x: true, linkedin: false }} onClose={() => {}} onChanged={() => {}} />);
    expect(screen.queryByText('Publish to LinkedIn')).not.toBeInTheDocument();
    expect(screen.getByText(/Connect LinkedIn in Settings/)).toBeInTheDocument();
  });

  it('counts characters against the channel limit', () => {
    render(<DraftDialog draft={{ ...draft, body: 'x'.repeat(600) }} publishing={{ x: true, linkedin: false }} onClose={() => {}} onChanged={() => {}} />);
    expect(screen.getByText(/about 3 posts as a thread/)).toBeInTheDocument();
  });
});
