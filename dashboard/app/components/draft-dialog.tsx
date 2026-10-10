'use client';

import { useEffect, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Check, ExternalLink, Rocket, Send, Trash2, X } from 'lucide-react';
import { clsx } from 'clsx';
import * as api from '../lib/api';
import { Badge, Button, inputClass, textareaClass } from './shared';

const CHANNEL_NAMES: Record<string, string> = {
  x: 'X', linkedin: 'LinkedIn', instagram: 'Instagram', youtube: 'YouTube', blog: 'Blog',
};
const LIMITS: Record<string, number> = { x: 280, linkedin: 3000 };

/** "212 / 280", "640 characters · about 3 posts as a thread" */
function lengthNote(channel: string, length: number): { text: string; over: boolean } {
  const limit = LIMITS[channel];
  if (!limit) return { text: `${length} characters`, over: false };
  if (channel === 'x' && length > limit) {
    return { text: `${length} characters · about ${Math.ceil(length / 270)} posts as a thread`, over: false };
  }
  return { text: `${length} / ${limit}`, over: length > limit };
}

/**
 * Review a content draft: edit it, then publish it straight to X or LinkedIn
 * (when connected), mark it as posted by hand, approve, or discard it.
 */
export function DraftDialog({ draft, publishing, onClose, onChanged }: {
  draft: api.MarketingContent | null;
  /** Channels the server can publish to */
  publishing?: { x: boolean; linkedin: boolean };
  onClose: () => void;
  onChanged: () => void;
}) {
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [postedUrl, setPostedUrl] = useState<string | null>(null);

  useEffect(() => {
    setTitle(draft?.title ?? '');
    setBody(draft?.body ?? '');
    setConfirming(false);
    setError(null);
    setPostedUrl(draft?.posted_url ?? null);
  }, [draft]);

  if (!draft) return null;
  const channel = draft.channel;
  const name = CHANNEL_NAMES[channel] ?? channel;
  const canPublish = !!publishing?.[channel as 'x' | 'linkedin'];
  const dirty = title !== draft.title || body !== draft.body;
  const note = lengthNote(channel, body.length);

  const act = async (key: string, fn: () => Promise<unknown>, close = true) => {
    setBusy(key);
    setError(null);
    try {
      if (dirty) await api.marketingContent.update(draft.id, { title, body });
      await fn();
      onChanged();
      if (close) onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
    } finally {
      setBusy(null);
      setConfirming(false);
    }
  };

  const publish = () => act('publish', async () => {
    const { posted_url } = await api.marketingContent.publish(draft.id);
    setPostedUrl(posted_url);
  }, false);

  return (
    <Dialog.Root open={!!draft} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40 backdrop-blur-[2px] z-50" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed left-1/2 top-[8%] -translate-x-1/2 w-[calc(100%-2rem)] max-w-xl bg-mc-panel rounded-xl shadow-dropdown z-50 animate-fade-up flex flex-col max-h-[84vh]"
        >
          <div className="flex items-center gap-2 px-5 h-12 border-b border-mc-line flex-shrink-0">
            <Dialog.Title className="text-sm font-semibold text-mc-text">Draft for {name}</Dialog.Title>
            <Badge variant={draft.status === 'approved' ? 'success' : draft.status === 'posted' ? 'accent' : 'default'}>{draft.status}</Badge>
            <span className="flex-1" />
            <Dialog.Close aria-label="Close" className="w-7 h-7 rounded-md flex items-center justify-center text-mc-muted hover:text-mc-text hover:bg-mc-hover cursor-pointer">
              <X size={16} />
            </Dialog.Close>
          </div>

          <div className="p-5 space-y-3 overflow-y-auto">
            <input aria-label="Title" className={clsx(inputClass, 'font-medium')} value={title} onChange={(e) => setTitle(e.target.value)} />
            <textarea
              aria-label="Post"
              rows={10}
              className={clsx(textareaClass, 'leading-relaxed')}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
            <div className="flex items-center justify-between text-2xs">
              <span className={note.over ? 'text-red-600 dark:text-red-400' : 'text-mc-dim'}>{note.text}</span>
              {!canPublish && LIMITS[channel] && (
                <span className="text-mc-dim">Connect {name} in Settings to publish from here</span>
              )}
            </div>
            {postedUrl && (
              <a href={postedUrl} target="_blank" rel="noreferrer"
                className="flex items-center gap-2 rounded-lg bg-emerald-500/10 ring-1 ring-emerald-500/20 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-400 hover:underline">
                <Check size={14} /> Posted on {name} <ExternalLink size={12} />
              </a>
            )}
            {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
          </div>

          {draft.status !== 'posted' && !postedUrl && (
            <div className="flex flex-wrap items-center gap-2 px-5 py-3 border-t border-mc-line flex-shrink-0">
              <Button variant="ghost" icon={Trash2} disabled={!!busy} loading={busy === 'discard'}
                onClick={() => act('discard', () => api.marketingContent.update(draft.id, { status: 'archived' }))}>Discard</Button>
              <span className="flex-1" />
              {confirming ? (
                <>
                  <span className="text-xs text-mc-muted">Publish publicly to {name}?</span>
                  <Button variant="ghost" onClick={() => setConfirming(false)}>Cancel</Button>
                  <Button variant="primary" icon={Rocket} loading={busy === 'publish'} onClick={publish}>Yes, publish</Button>
                </>
              ) : (
                <>
                  <Button icon={Send} disabled={!!busy} loading={busy === 'posted'}
                    onClick={() => act('posted', () => api.marketingContent.update(draft.id, { status: 'posted' }))}>Mark as posted</Button>
                  {draft.status === 'draft' && (
                    <Button icon={Check} disabled={!!busy} loading={busy === 'approve'}
                      onClick={() => act('approve', () => api.marketingContent.update(draft.id, { status: 'approved' }))}>Approve</Button>
                  )}
                  {canPublish ? (
                    <Button variant="primary" icon={Rocket} disabled={!!busy || note.over || !body.trim()} onClick={() => setConfirming(true)}>
                      Publish to {name}
                    </Button>
                  ) : dirty && (
                    <Button variant="primary" loading={busy === 'save'} onClick={() => act('save', async () => {}, false)}>Save</Button>
                  )}
                </>
              )}
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
