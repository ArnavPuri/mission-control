'use client';

import { Zap } from 'lucide-react';
import { AgentBuilderForm } from '../builder-form';

export default function NewAgentPage() {
  return (
    <div className="min-h-screen bg-mc-bg dark:bg-gray-950 transition-colors">
      <header className="px-4 sm:px-6 lg:px-8 py-3 bg-white dark:bg-gray-900 border-b border-mc-border dark:border-gray-800 sticky top-0 z-30">
        <div className="max-w-[1600px] mx-auto flex items-center gap-3">
          <Zap size={18} className="text-mc-accent" />
          <h1 className="text-base font-bold text-mc-text dark:text-gray-100">Create Agent</h1>
        </div>
      </header>

      <main className="max-w-[900px] mx-auto px-4 sm:px-6 lg:px-8 py-6 pb-24">
        <AgentBuilderForm showTemplates={true} />
      </main>
    </div>
  );
}
