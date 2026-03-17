import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Mission Control',
  description: 'Personal AI-powered command center',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
