import './globals.css';
import type { Metadata } from 'next';
import { AppShell } from './components/app-shell';
import { themeInitScript } from './components/shared';

export const metadata: Metadata = {
  title: 'Mission Control',
  description: 'Your projects, tasks and AI agents in one place',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        <link
          rel="icon"
          href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='8' fill='%235e5ce6'/><text x='16' y='21' font-family='Arial' font-size='13' font-weight='700' fill='white' text-anchor='middle'>MC</text></svg>"
        />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
