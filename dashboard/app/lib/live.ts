/**
 * One WebSocket for the whole app. Components subscribe to backend events
 * ("task.created", "agent.completed", ...) instead of each opening a socket.
 */
import { useEffect, useState } from 'react';
import { connectWebSocket } from './api';

type LiveEvent = { type: string; data: any };
type Listener = (event: LiveEvent) => void;

const listeners = new Set<Listener>();
let socket: WebSocket | null = null;

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  if (!socket && typeof window !== 'undefined') {
    socket = connectWebSocket((event) => listeners.forEach((l) => l(event)));
  }
  return () => {
    listeners.delete(listener);
  };
}

/** The latest step of each agent run that's working on a task, by task id. */
export function useLatestSteps(): Record<string, string> {
  const [steps, setSteps] = useState<Record<string, string>>({});
  useEffect(() => subscribe(({ type, data }) => {
    if (type === 'run.progress' && data?.task_id && data.steps?.length) {
      setSteps((s) => ({ ...s, [data.task_id]: data.steps[data.steps.length - 1] }));
    } else if (type === 'task.updated' && data?.id) {
      // The agent replied (or the task changed): its last step is stale
      setSteps((s) => {
        if (!(data.id in s)) return s;
        const { [data.id]: _, ...rest } = s;
        return rest;
      });
    }
  }), []);
  return steps;
}
