import type { JSX } from 'react';

import { useHealth } from '@/api/queries';

const BackendStatus = (): JSX.Element => {
  const { isPending, isError } = useHealth();

  const message = isPending
    ? 'Checking backend…'
    : isError
      ? 'Backend unavailable'
      : 'Backend connected';

  const tone = isPending
    ? 'bg-slate-100 text-slate-700'
    : isError
      ? 'bg-red-100 text-red-800'
      : 'bg-emerald-100 text-emerald-800';

  return (
    <p role="status" aria-live="polite" className={`inline-block rounded-md px-3 py-1 ${tone}`}>
      {message}
    </p>
  );
};

export const App = (): JSX.Element => (
  <div className="min-h-screen bg-slate-50 text-slate-900">
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto max-w-4xl px-6 py-4">
        <h1 className="text-xl font-semibold">Finance Tracker</h1>
      </div>
    </header>

    <main role="main" className="mx-auto max-w-4xl px-6 py-10">
      <h2 className="text-2xl font-semibold">Phase 0 — foundations</h2>
      <p className="mt-2 max-w-prose text-slate-600">
        The application shell, CI/CD pipeline and deployment path are in place. Accounts,
        transactions, budgets and investments arrive in the phases that follow.
      </p>
      <div className="mt-6">
        <BackendStatus />
      </div>
    </main>
  </div>
);
