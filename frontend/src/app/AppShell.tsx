import { useState, type JSX } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';

import { Badge, Button } from '@/components/ui';
import { logout, useAuthStore } from '@/features/auth/store';

const navItems = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/transactions', label: 'Transactions', end: false },
  { to: '/budgets', label: 'Budgets', end: false },
  { to: '/investments', label: 'Investments', end: false },
  { to: '/reports', label: 'Reports', end: false },
  { to: '/recurring', label: 'Recurring', end: false },
  { to: '/accounts', label: 'Accounts', end: false },
  { to: '/categories', label: 'Categories', end: false },
  { to: '/settings', label: 'Settings & export', end: false },
] as const;

const navLinkClass = ({ isActive }: { isActive: boolean }): string =>
  `block rounded-md px-3 py-2 text-sm font-medium transition ${
    isActive ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-100'
  }`;

export const AppShell = (): JSX.Element => {
  const user = useAuthStore((state) => state.user);
  const navigate = useNavigate();
  const [loggingOut, setLoggingOut] = useState(false);

  const onLogout = async (): Promise<void> => {
    setLoggingOut(true);
    try {
      await logout();
      void navigate('/login', { replace: true });
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-4 focus:py-2 focus:text-sm"
      >
        Skip to content
      </a>

      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-slate-200 bg-white p-6 lg:block">
        <p className="text-lg font-semibold tracking-tight">Finance Tracker</p>
        <p className="mt-1 text-xs text-slate-500">Multi-currency personal finance</p>
        <nav aria-label="Main navigation" className="mt-8 space-y-1">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={navLinkClass}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
            <div>
              <p className="text-sm font-semibold lg:hidden">Finance Tracker</p>
              <p className="text-sm text-slate-600">
                {user?.display_name ?? 'Signed in'}
                {user !== null ? (
                  <span className="ml-2 inline-block align-middle">
                    <Badge tone="info">{user.base_currency}</Badge>
                  </span>
                ) : null}
              </p>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void onLogout()}
              isLoading={loggingOut}
            >
              Sign out
            </Button>
          </div>
          <nav
            aria-label="Mobile navigation"
            className="flex gap-2 overflow-x-auto px-4 pb-3 lg:hidden"
          >
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={navLinkClass}>
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>

        <main id="main-content" role="main" className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
