import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockFetch = vi.fn();
global.fetch = mockFetch;

import * as api from '../app/lib/api';

function mockResponse(data: any, ok = true) {
  return {
    ok,
    json: () => Promise.resolve(data),
    statusText: 'OK',
  };
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe('API Client', () => {
  describe('projects', () => {
    it('lists projects', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse([{ id: '1', name: 'Test' }]));
      const result = await api.projects.list();
      expect(result).toHaveLength(1);
      expect(result[0].name).toBe('Test');
    });

    it('creates a project', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({ id: 'new-id' }));
      const result = await api.projects.create({ name: 'New' });
      expect(result.id).toBe('new-id');
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/projects'),
        expect.objectContaining({ method: 'POST' }),
      );
    });
  });

  describe('tasks', () => {
    it('lists tasks', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse([{ id: '1', text: 'Task 1' }]));
      const result = await api.tasks.list();
      expect(result).toHaveLength(1);
    });

    it('creates a task', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({ id: 'task-1' }));
      const result = await api.tasks.create({ text: 'Do thing' });
      expect(result.id).toBe('task-1');
    });

    it('updates a task', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({ updated: true }));
      const result = await api.tasks.update('t1', { status: 'done' });
      expect(result.updated).toBe(true);
    });

    it('deletes a task', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({ deleted: true }));
      const result = await api.tasks.delete('t1');
      expect(result.deleted).toBe(true);
    });
  });

  describe('notes', () => {
    it('lists notes', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse([{ id: 'n1', title: 'Note 1' }]));
      const result = await api.notes.list();
      expect(result).toHaveLength(1);
    });

    it('creates a note', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({ id: 'n1' }));
      const result = await api.notes.create({ title: 'New Note' });
      expect(result.id).toBe('n1');
    });
  });

  describe('error handling', () => {
    it('throws on API error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: () => Promise.resolve({ detail: 'Not found' }),
      });
      await expect(api.projects.list()).rejects.toThrow('Not found');
    });
  });
});
