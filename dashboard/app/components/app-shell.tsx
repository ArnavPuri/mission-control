'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { AlertTriangle } from 'lucide-react';
import * as api from '../lib/api';
import { Spinner } from './shared';
import { CommandMenu } from './command-menu';
import { MobileNav, Sidebar } from './nav';
import { ProjectDialog } from './project-dialog';
import { TaskDialog } from './task-dialog';
import { WorkspaceProvider, useWorkspace } from './workspace';

/** Dialogs that any page can open through the workspace context. */
function GlobalDialogs({ taskId, setTaskId, project, setProject, commandOpen, setCommandOpen }: {
  taskId: string | null; setTaskId: (id: string | null) => void;
  project: api.Project | null; setProject: (p: api.Project | null) => void;
  commandOpen: boolean; setCommandOpen: (v: boolean) => void;
}) {
  const { agents, projects, tick, refresh } = useWorkspace();
  return (
    <>
      <TaskDialog
        taskId={taskId}
        agents={agents}
        projects={projects}
        refreshTick={tick}
        onClose={() => setTaskId(null)}
        onChanged={refresh}
      />
      <ProjectDialog project={project} onClose={() => setProject(null)} onSaved={refresh} />
      <CommandMenu open={commandOpen} onOpenChange={setCommandOpen} />
    </>
  );
}

function isLocalhost() {
  return typeof window !== 'undefined' && ['localhost', '127.0.0.1', '[::1]'].includes(window.location.hostname);
}

/** Login gate: shows the app once signed in (or when no password is configured). */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [auth, setAuth] = useState<api.AuthState | null>(null);
  const [apiDown, setApiDown] = useState(false);

  useEffect(() => {
    if (pathname === '/login') return;
    api.auth.me()
      .then((state) => {
        if (state.auth_enabled && !state.authenticated) {
          window.location.href = `/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;
        } else {
          setAuth(state);
        }
      })
      .catch(() => setApiDown(true));
  }, [pathname]);

  if (pathname === '/login') return <>{children}</>;
  if (apiDown) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-2 text-sm text-mc-muted">
        <AlertTriangle size={18} className="text-amber-500" />
        Can&apos;t reach the Mission Control API. Is the backend running?
      </div>
    );
  }
  if (!auth) return <div className="min-h-screen flex items-center justify-center"><Spinner size={20} /></div>;
  return <Workspace authEnabled={auth.auth_enabled}>{children}</Workspace>;
}

function Workspace({ children, authEnabled }: { children: React.ReactNode; authEnabled: boolean }) {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [project, setProject] = useState<api.Project | null>(null);
  const [commandOpen, setCommandOpen] = useState(false);

  const openCommandMenu = useCallback(() => setCommandOpen(true), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setCommandOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <WorkspaceProvider onOpenTask={setTaskId} onOpenProject={setProject} onOpenCommandMenu={openCommandMenu}>
      <Suspense fallback={null}>
        <Sidebar authEnabled={authEnabled} />
        <MobileNav authEnabled={authEnabled} />
      </Suspense>
      <div className="md:pl-60 min-h-screen">
        {!authEnabled && !isLocalhost() && (
          <div className="flex items-center gap-2 px-4 sm:px-8 py-2 bg-amber-500/10 text-amber-800 dark:text-amber-300 text-xs border-b border-amber-500/20">
            <AlertTriangle size={13} />
            No DASHBOARD_PASSWORD is set: anyone who can open this page can use Mission Control. Set it in .env and restart.
          </div>
        )}
        {children}
      </div>
      <GlobalDialogs
        taskId={taskId} setTaskId={setTaskId}
        project={project} setProject={setProject}
        commandOpen={commandOpen} setCommandOpen={setCommandOpen}
      />
    </WorkspaceProvider>
  );
}
