import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest';

import { AppRoutes } from '@/app/App';
import { AuthShell } from '@/app/AuthShell';
import { resetAuthForTests, useAuthStore } from '@/features/auth/store';
import { installApi, jsonResponse, noContentResponse, user } from './helpers/api';
import { renderWithProviders } from './helpers/render';

beforeEach(() => {
  resetAuthForTests();
  useAuthStore.setState({ status: 'authenticated', user });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('Authenticated shell', () => {
  it('renders the primary navigation', () => {
    installApi([]);
    renderWithProviders(<AppRoutes />, { route: '/accounts' });

    expect(screen.getByRole('navigation', { name: /main navigation/i })).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Budgets' })[0]).toHaveAttribute('href', '/budgets');
    expect(screen.getByRole('heading', { name: 'Accounts' })).toBeInTheDocument();
  });

  it('shows the signed-in user and base currency', () => {
    installApi([]);
    renderWithProviders(<AppRoutes />, { route: '/' });

    expect(screen.getByText(/Ada Lovelace/)).toBeInTheDocument();
    expect(screen.getByText('GBP')).toBeInTheDocument();
  });

  it('signs out and returns to the login screen', async () => {
    installApi([{ method: 'POST', path: '/api/v1/auth/logout', response: noContentResponse() }]);
    renderWithProviders(<AppRoutes />, { route: '/' });

    await userEvent.click(screen.getByRole('button', { name: /sign out/i }));

    await waitFor(() => expect(useAuthStore.getState().status).toBe('anonymous'));
    expect(await screen.findByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('does not render protected content for an anonymous user', () => {
    installApi([]);
    useAuthStore.setState({ status: 'anonymous', user: null });

    renderWithProviders(<AppRoutes />, { route: '/budgets' });

    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('boots from the refresh cookie before rendering routes', async () => {
    installApi([
      {
        method: 'POST',
        path: '/api/v1/auth/refresh',
        response: jsonResponse({ access_token: 'token', token_type: 'bearer', expires_in: 900 }),
      },
      { method: 'GET', path: '/api/v1/auth/me', response: jsonResponse(user) },
    ]);
    resetAuthForTests();

    renderWithProviders(
      <AuthShell>
        <AppRoutes />
      </AuthShell>,
      { route: '/' },
    );

    expect(screen.getByText(/restoring your session/i)).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
  });

  it('renders a not-found page for unknown routes', () => {
    installApi([]);
    renderWithProviders(<AppRoutes />, { route: '/does-not-exist' });

    expect(screen.getByRole('heading', { name: /page not found/i })).toBeInTheDocument();
  });
});

describe('ProtectedRoute booting branch', () => {
  it('shows the session restore state while booting', () => {
    useAuthStore.setState({ status: 'booting', user: null });
    renderWithProviders(<AppRoutes />, { route: '/' });

    expect(screen.getByText(/restoring your session/i)).toBeInTheDocument();
  });
});
