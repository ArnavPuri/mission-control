'use client';

import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Lock } from 'lucide-react';
import * as api from '../lib/api';
import { Button, inputClass } from '../components/shared';

function LoginForm() {
  const params = useSearchParams();
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.auth.login(password);
      const next = params.get('next');
      // Only same-site paths, never an absolute URL
      window.location.href = next && next.startsWith('/') && !next.startsWith('//') ? next : '/';
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not sign in');
      setBusy(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center px-4 bg-mc-canvas">
      <form onSubmit={submit} className="w-full max-w-sm bg-mc-panel rounded-xl shadow-dropdown p-6 animate-fade-up">
        <div className="flex items-center gap-2.5 mb-6">
          <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-mc-accent to-violet-500 text-white flex items-center justify-center text-xs font-bold">MC</span>
          <div>
            <h1 className="text-sm font-semibold text-mc-text">Mission Control</h1>
            <p className="text-xs text-mc-muted">Sign in to your dashboard</p>
          </div>
        </div>
        <label htmlFor="password" className="block text-xs font-medium text-mc-muted mb-1.5">Password</label>
        <div className="relative">
          <Lock size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-mc-dim" />
          <input
            id="password"
            type="password"
            autoFocus
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={`${inputClass} pl-8`}
          />
        </div>
        {error && <p className="text-xs text-red-600 dark:text-red-400 mt-2">{error}</p>}
        <Button type="submit" variant="primary" loading={busy} disabled={!password} className="w-full mt-4">Sign in</Button>
        <p className="text-2xs text-mc-dim mt-4">The password is <code className="font-mono">DASHBOARD_PASSWORD</code> in your server&apos;s <code className="font-mono">.env</code>.</p>
      </form>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
