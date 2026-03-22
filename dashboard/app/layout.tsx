import './globals.css';
import type { Metadata } from 'next';
import { Sidebar, MobileNav } from './components/nav';

export const metadata: Metadata = {
  title: 'Mission Control',
  description: 'Personal AI-powered command center',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a href="#main-content" className="skip-to-content">
          Skip to main content
        </a>
        <Sidebar />
        <MobileNav />
        <main id="main-content" className="md:ml-14 pb-16 md:pb-0">
          {children}
        </main>
      </body>
    </html>
  );
}
