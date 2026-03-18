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
        <Sidebar />
        <MobileNav />
        <div className="md:ml-14 pb-16 md:pb-0">
          {children}
        </div>
      </body>
    </html>
  );
}
