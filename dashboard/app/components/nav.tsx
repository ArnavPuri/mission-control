'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { clsx } from 'clsx';
import {
  LayoutDashboard, FolderOpen, Zap, PenLine, Settings, Keyboard,
  Sun, Moon, Megaphone,
} from 'lucide-react';
import { useTheme, type Theme } from './shared';
import * as Tooltip from '@radix-ui/react-tooltip';
import { useState } from 'react';

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard, shortcut: 'g d' },
  { href: '/projects', label: 'Projects', icon: FolderOpen, shortcut: 'g p' },
  { href: '/marketing', label: 'Marketing', icon: Megaphone, shortcut: 'g m' },
  { href: '/agents', label: 'Agents', icon: Zap, shortcut: 'g a' },
  { href: '/journal', label: 'Journal', icon: PenLine, shortcut: 'g j' },
  { href: '/settings', label: 'Settings', icon: Settings, shortcut: 'g s' },
];

export function Sidebar() {
  const pathname = usePathname();
  const [theme, setTheme] = useTheme();
  const [showShortcuts, setShowShortcuts] = useState(false);

  return (
    <Tooltip.Provider delayDuration={300}>
      <aside className="fixed left-0 top-0 bottom-0 w-14 bg-white dark:bg-gray-900 border-r border-mc-border dark:border-gray-800 flex flex-col items-center py-4 z-40">
        {/* Logo */}
        <Link href="/" className="w-9 h-9 rounded-xl bg-mc-accent text-white flex items-center justify-center font-bold text-sm mb-6 hover:bg-blue-700 transition-colors">
          MC
        </Link>

        {/* Nav items */}
        <nav className="flex flex-col gap-1.5 flex-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
            return (
              <Tooltip.Root key={item.href}>
                <Tooltip.Trigger asChild>
                  <Link
                    href={item.href}
                    className={clsx(
                      'w-10 h-10 rounded-lg flex items-center justify-center transition-all',
                      isActive
                        ? 'bg-mc-accent-light dark:bg-blue-950 text-mc-accent dark:text-blue-400'
                        : 'text-mc-muted dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-mc-text dark:hover:text-gray-300'
                    )}
                  >
                    <item.icon size={18} />
                  </Link>
                </Tooltip.Trigger>
                <Tooltip.Content side="right" className="bg-mc-text dark:bg-gray-700 text-white text-xs px-2.5 py-1.5 rounded-md" sideOffset={8}>
                  {item.label}
                  <span className="text-gray-400 ml-2 font-mono">{item.shortcut}</span>
                </Tooltip.Content>
              </Tooltip.Root>
            );
          })}
        </nav>

        {/* Bottom actions */}
        <div className="flex flex-col gap-1.5">
          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <button
                onClick={() => setShowShortcuts(!showShortcuts)}
                className="w-10 h-10 rounded-lg flex items-center justify-center text-mc-muted dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-mc-text dark:hover:text-gray-300 transition-all cursor-pointer bg-transparent border-none"
              >
                <Keyboard size={18} />
              </button>
            </Tooltip.Trigger>
            <Tooltip.Content side="right" className="bg-mc-text dark:bg-gray-700 text-white text-xs px-2.5 py-1.5 rounded-md" sideOffset={8}>
              Shortcuts
            </Tooltip.Content>
          </Tooltip.Root>

          <Tooltip.Root>
            <Tooltip.Trigger asChild>
              <button
                onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
                className="w-10 h-10 rounded-lg flex items-center justify-center text-mc-muted dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-mc-text dark:hover:text-gray-300 transition-all cursor-pointer bg-transparent border-none"
              >
                {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
              </button>
            </Tooltip.Trigger>
            <Tooltip.Content side="right" className="bg-mc-text dark:bg-gray-700 text-white text-xs px-2.5 py-1.5 rounded-md" sideOffset={8}>
              {theme === 'light' ? 'Dark mode' : 'Light mode'}
            </Tooltip.Content>
          </Tooltip.Root>
        </div>
      </aside>

      {/* Keyboard shortcuts overlay */}
      {showShortcuts && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={() => setShowShortcuts(false)}>
          <div className="bg-white dark:bg-gray-900 rounded-xl border border-mc-border dark:border-gray-800 shadow-xl p-6 max-w-sm w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-mc-text dark:text-gray-100">Keyboard Shortcuts</h3>
              <button onClick={() => setShowShortcuts(false)} className="text-mc-dim hover:text-mc-text cursor-pointer bg-transparent border-none">
                <span className="text-xs">ESC</span>
              </button>
            </div>
            <div className="flex flex-col gap-2 text-sm">
              <div className="text-[11px] font-medium text-mc-dim uppercase tracking-wide">Navigation</div>
              {navItems.map((item) => (
                <div key={item.href} className="flex items-center justify-between py-1">
                  <span className="text-mc-secondary dark:text-gray-300">{item.label}</span>
                  <kbd className="text-xs text-mc-dim border border-mc-border dark:border-gray-700 rounded px-1.5 py-0.5 font-mono bg-gray-50 dark:bg-gray-800">{item.shortcut}</kbd>
                </div>
              ))}
              <div className="text-[11px] font-medium text-mc-dim uppercase tracking-wide mt-2">Actions</div>
              {[
                { label: 'Command palette', key: 'Cmd+K' },
                { label: 'New task', key: 'n t' },
                { label: 'New idea', key: 'n i' },
                { label: 'New note', key: 'n o' },
                { label: 'Toggle theme', key: 'Shift+T' },
                { label: 'Close dialog', key: 'Esc' },
              ].map((s) => (
                <div key={s.key} className="flex items-center justify-between py-1">
                  <span className="text-mc-secondary dark:text-gray-300">{s.label}</span>
                  <kbd className="text-xs text-mc-dim border border-mc-border dark:border-gray-700 rounded px-1.5 py-0.5 font-mono bg-gray-50 dark:bg-gray-800">{s.key}</kbd>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </Tooltip.Provider>
  );
}

export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-white dark:bg-gray-900 border-t border-mc-border dark:border-gray-800 flex items-center justify-around py-2 z-40 md:hidden">
      {navItems.map((item) => {
        const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
        return (
          <Link
            key={item.href}
            href={item.href}
            className={clsx(
              'flex flex-col items-center gap-0.5 px-3 py-1 rounded-lg transition-colors',
              isActive ? 'text-mc-accent' : 'text-mc-muted dark:text-gray-500'
            )}
          >
            <item.icon size={20} />
            <span className="text-[10px] font-medium">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
