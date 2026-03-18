import '@testing-library/jest-dom';

// Mock fetch globally
global.fetch = vi.fn();

// Mock localStorage
const store: Record<string, string> = {};
Object.defineProperty(window, 'localStorage', {
  value: {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: vi.fn((key: string) => { delete store[key]; }),
    clear: vi.fn(() => { Object.keys(store).forEach(k => delete store[k]); }),
  },
});

// Mock WebSocket
class MockWebSocket {
  onmessage: ((e: any) => void) | null = null;
  onclose: (() => void) | null = null;
  close() {}
}
(global as any).WebSocket = MockWebSocket;
