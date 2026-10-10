'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import * as api from '../lib/api';
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

export function AppShell({ children }: { children: React.ReactNode }) {
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
        <Sidebar />
        <MobileNav />
      </Suspense>
      <div className="md:pl-60 min-h-screen">{children}</div>
      <GlobalDialogs
        taskId={taskId} setTaskId={setTaskId}
        project={project} setProject={setProject}
        commandOpen={commandOpen} setCommandOpen={setCommandOpen}
      />
    </WorkspaceProvider>
  );
}
