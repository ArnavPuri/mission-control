/**
 * One WebSocket for the whole app. Components subscribe to backend events
 * ("task.created", "agent.completed", ...) instead of each opening a socket.
 */
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
