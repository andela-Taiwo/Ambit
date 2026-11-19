import type { JSX } from 'react';
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom';

import { AuthShell } from '@/app/AuthShell';
import { AppShell } from '@/app/AppShell';
import { ProtectedRoute } from '@/app/ProtectedRoute';
import { LoginPage, RegisterPage } from '@/features/auth/AuthPages';
import { AccountsPage } from '@/pages/AccountsPage';
import { BudgetsPage } from '@/pages/BudgetsPage';
import { CategoriesPage } from '@/pages/CategoriesPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { InvestmentsPage } from '@/pages/InvestmentsPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { RecurringPage } from '@/pages/RecurringPage';
import { ReportsPage } from '@/pages/ReportsPage';
import { TransactionsPage } from '@/pages/TransactionsPage';

const NotFoundPage = (): JSX.Element => (
  <div className="mx-auto max-w-lg py-24 text-center">
    <h1 className="text-2xl font-semibold">Page not found</h1>
    <p className="mt-2 text-sm text-slate-600">That page does not exist.</p>
    <Link className="mt-4 inline-block text-sm font-medium underline" to="/">
      Back to the dashboard
    </Link>
  </div>
);

export const AppRoutes = (): JSX.Element => (
  <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/register" element={<RegisterPage />} />
    <Route element={<ProtectedRoute />}>
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="transactions" element={<TransactionsPage />} />
        <Route path="budgets" element={<BudgetsPage />} />
        <Route path="investments" element={<InvestmentsPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="recurring" element={<RecurringPage />} />
        <Route path="accounts" element={<AccountsPage />} />
        <Route path="categories" element={<CategoriesPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Route>
    <Route path="*" element={<NotFoundPage />} />
  </Routes>
);

export const App = (): JSX.Element => (
  <BrowserRouter>
    <AuthShell>
      <AppRoutes />
    </AuthShell>
  </BrowserRouter>
);
