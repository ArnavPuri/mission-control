'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { clsx } from 'clsx';

/** Renders agent replies and notes (GitHub-flavored markdown: tables, lists, links). */
export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={clsx('md', className)}>
      <ReactMarkdown
        // singleTilde off: agents write "~$19" meaning "about", not strikethrough
        remarkPlugins={[[remarkGfm, { singleTilde: false }]]}
        components={{
          a: ({ href, children: c }) => <a href={href} target="_blank" rel="noreferrer">{c}</a>,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
