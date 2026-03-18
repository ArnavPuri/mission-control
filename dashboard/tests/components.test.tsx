import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Card, Badge, EmptyState, StatCard } from '../app/components/shared';
import { FolderOpen } from 'lucide-react';

describe('Shared Components', () => {
  describe('Card', () => {
    it('renders children', () => {
      render(<Card>Hello</Card>);
      expect(screen.getByText('Hello')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(<Card className="p-4">Test</Card>);
      expect(container.firstChild).toHaveClass('p-4');
    });
  });

  describe('Badge', () => {
    it('renders text', () => {
      render(<Badge>todo</Badge>);
      expect(screen.getByText('todo')).toBeInTheDocument();
    });

    it('applies variant styles', () => {
      const { container } = render(<Badge variant="success">done</Badge>);
      const badge = container.firstChild as HTMLElement;
      expect(badge.className).toContain('emerald');
    });
  });

  describe('EmptyState', () => {
    it('renders message', () => {
      render(<EmptyState icon={FolderOpen} message="Nothing here" />);
      expect(screen.getByText('Nothing here')).toBeInTheDocument();
    });

    it('applies small variant', () => {
      const { container } = render(<EmptyState icon={FolderOpen} message="Empty" small />);
      expect(container.firstChild).toHaveClass('py-6');
    });
  });

  describe('StatCard', () => {
    it('renders label and value', () => {
      render(<StatCard label="Tasks" value={42} />);
      expect(screen.getByText('Tasks')).toBeInTheDocument();
      expect(screen.getByText('42')).toBeInTheDocument();
    });

    it('applies accent style', () => {
      const { container } = render(<StatCard label="Active" value={3} accent />);
      expect(container.innerHTML).toContain('mc-accent');
    });
  });
});
