import type { JSX } from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LoginPage, RegisterPage } from '@/features/auth/AuthPages';
import { resetAuthForTests, useAuthStore } from '@/features/auth/store';
import { jsonResponse, installApi, user } from './helpers/api';
import { renderRoutes } from './helpers/render';

const Home = (): JSX.Element => <p>home screen</p>;

const authRoutes = (): JSX.Element => (
  <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/register" element={<RegisterPage />} />
    <Route path="/" element={<Home />} />
  </Routes>
);

beforeEach(() => {
  resetAuthForTests();
  useAuthStore.setState({ status: 'anonymous', user: null });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('LoginPage', () => {
  it('signs in and navigates home', async () => {
    installApi([
      {
        method: 'POST',
        path: '/api/v1/auth/login',
        response: jsonResponse({ access_token: 'token', token_type: 'bearer', expires_in: 900 }),
      },
      { method: 'GET', path: '/api/v1/auth/me', response: jsonResponse(user) },
    ]);
    renderRoutes(authRoutes(), '/login');

    await userEvent.type(screen.getByLabelText(/email/i), 'ada@example.com');
    await userEvent.type(screen.getByLabelText(/password/i), 'correct-horse-battery-staple');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText('home screen')).toBeInTheDocument();
    expect(useAuthStore.getState().status).toBe('authenticated');
  });

  it('shows the API error when credentials are rejected', async () => {
    installApi([
      {
        method: 'POST',
        path: '/api/v1/auth/login',
        response: jsonResponse({ detail: 'Incorrect email or password' }, 401),
      },
    ]);
    renderRoutes(authRoutes(), '/login');

    await userEvent.type(screen.getByLabelText(/email/i), 'ada@example.com');
    await userEvent.type(screen.getByLabelText(/password/i), 'wrong-password');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/incorrect email or password/i);
  });

  it('redirects an already-authenticated user away from login', () => {
    useAuthStore.setState({ status: 'authenticated', user });
    renderRoutes(authRoutes(), '/login');

    expect(screen.getByText('home screen')).toBeInTheDocument();
  });
});

describe('RegisterPage', () => {
  it('validates the name and password before calling the API', async () => {
    const fetchMock = installApi([]);
    renderRoutes(authRoutes(), '/register');

    await userEvent.type(screen.getByLabelText(/^name$/i), ' ');
    await userEvent.type(screen.getByLabelText(/password/i), 'short');
    await userEvent.click(screen.getByRole('button', { name: /create account/i }));

    expect(await screen.findByText(/enter your name/i)).toBeInTheDocument();
    expect(screen.getByText(/use at least 12 characters/i)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('registers and signs the new user in', async () => {
    installApi([
      { method: 'POST', path: '/api/v1/auth/register', response: jsonResponse(user, 201) },
      {
        method: 'POST',
        path: '/api/v1/auth/login',
        response: jsonResponse({ access_token: 'token', token_type: 'bearer', expires_in: 900 }),
      },
      { method: 'GET', path: '/api/v1/auth/me', response: jsonResponse(user) },
    ]);
    renderRoutes(authRoutes(), '/register');

    await userEvent.type(screen.getByLabelText(/^name$/i), 'Ada Lovelace');
    await userEvent.type(screen.getByLabelText(/email/i), 'ada@example.com');
    await userEvent.type(screen.getByLabelText(/password/i), 'correct-horse-battery-staple');
    await userEvent.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => expect(useAuthStore.getState().status).toBe('authenticated'));
    expect(await screen.findByText('home screen')).toBeInTheDocument();
  });

  it('links to the login page', () => {
    renderRoutes(authRoutes(), '/register');

    expect(screen.getByRole('link', { name: /sign in/i })).toHaveAttribute('href', '/login');
  });
});

describe('Auth edge cases', () => {
  it('submits the selected base currency when registering', async () => {
    const localFetch = installApi([
      { method: 'POST', path: '/api/v1/auth/register', response: jsonResponse(user, 201) },
      {
        method: 'POST',
        path: '/api/v1/auth/login',
        response: jsonResponse({ access_token: 'token', token_type: 'bearer', expires_in: 900 }),
      },
      { method: 'GET', path: '/api/v1/auth/me', response: jsonResponse(user) },
    ]);
    renderRoutes(authRoutes(), '/register');

    await userEvent.type(screen.getByLabelText(/^name$/i), 'Ada Lovelace');
    await userEvent.type(screen.getByLabelText(/email/i), 'ada@example.com');
    await userEvent.type(screen.getByLabelText(/password/i), 'correct-horse-battery-staple');
    await userEvent.selectOptions(screen.getByLabelText(/base currency/i), 'NGN');
    await userEvent.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      const registerCall = localFetch.mock.calls.find(([input]) =>
        (typeof input === 'string' ? input : input.toString()).endsWith('/auth/register'),
      );
      expect(JSON.parse(String(registerCall?.[1]?.body))).toMatchObject({ base_currency: 'NGN' });
    });
  });

  it('shows a register API error', async () => {
    installApi([
      {
        method: 'POST',
        path: '/api/v1/auth/register',
        response: jsonResponse({ detail: 'Email already used' }, 409),
      },
    ]);
    renderRoutes(authRoutes(), '/register');

    await userEvent.type(screen.getByLabelText(/^name$/i), 'Ada Lovelace');
    await userEvent.type(screen.getByLabelText(/email/i), 'ada@example.com');
    await userEvent.type(screen.getByLabelText(/password/i), 'correct-horse-battery-staple');
    await userEvent.click(screen.getByRole('button', { name: /create account/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Email already used');
  });
});
