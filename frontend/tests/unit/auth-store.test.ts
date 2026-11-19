import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { getAccessToken, setAccessToken } from '@/api/client';
import {
  bootstrapAuth,
  login,
  logout,
  register,
  resetAuthForTests,
  useAuthStore,
} from '@/features/auth/store';

const user = {
  id: 'u1',
  email: 'ada@example.com',
  display_name: 'Ada',
  base_currency: 'GBP',
};

const json = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const token = { access_token: 'access', token_type: 'bearer', expires_in: 900 };

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>;

beforeEach(() => {
  resetAuthForTests();
  fetchMock = vi.fn<typeof fetch>();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('bootstrapAuth', () => {
  it('restores a session from the refresh cookie', async () => {
    fetchMock.mockResolvedValueOnce(json(token)).mockResolvedValueOnce(json(user));

    await bootstrapAuth();

    expect(getAccessToken()).toBe('access');
    expect(useAuthStore.getState()).toMatchObject({ status: 'authenticated', user });
  });

  it('becomes anonymous when refresh fails', async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: 'nope' }, 401));

    await bootstrapAuth();

    expect(getAccessToken()).toBeNull();
    expect(useAuthStore.getState().status).toBe('anonymous');
  });

  it('becomes anonymous when the refreshed token cannot fetch the user', async () => {
    fetchMock.mockResolvedValueOnce(json(token)).mockResolvedValueOnce(json({ detail: 'no' }, 401));

    await bootstrapAuth();

    expect(getAccessToken()).toBeNull();
    expect(useAuthStore.getState().status).toBe('anonymous');
  });

  it('de-duplicates concurrent boots', async () => {
    fetchMock.mockResolvedValueOnce(json(token)).mockResolvedValueOnce(json(user));

    await Promise.all([bootstrapAuth(), bootstrapAuth()]);

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe('login', () => {
  it('stores the token and user after login', async () => {
    fetchMock.mockResolvedValueOnce(json(token)).mockResolvedValueOnce(json(user));

    await expect(login('ada@example.com', 'password')).resolves.toEqual(user);

    expect(getAccessToken()).toBe('access');
    expect(useAuthStore.getState().user).toEqual(user);
  });

  it('clears a partial session when /me fails', async () => {
    fetchMock
      .mockResolvedValueOnce(json(token))
      .mockResolvedValueOnce(json({ detail: 'unauthorised' }, 401))
      .mockResolvedValueOnce(json({ detail: 'nope' }, 401));

    await expect(login('ada@example.com', 'password')).rejects.toMatchObject({ status: 401 });

    expect(getAccessToken()).toBeNull();
    expect(useAuthStore.getState().status).toBe('anonymous');
  });
});

describe('register', () => {
  it('registers then logs in', async () => {
    fetchMock
      .mockResolvedValueOnce(json(user, 201))
      .mockResolvedValueOnce(json(token))
      .mockResolvedValueOnce(json(user));

    await expect(
      register({
        email: 'ada@example.com',
        password: 'correct-horse-battery-staple',
        display_name: 'Ada',
        base_currency: 'GBP',
      }),
    ).resolves.toEqual(user);

    expect(fetchMock.mock.calls[0]?.[0]).toBe('http://localhost:8000/api/v1/auth/register');
    expect(useAuthStore.getState().status).toBe('authenticated');
  });
});

describe('logout', () => {
  it('clears local state even when the request fails', async () => {
    setAccessToken('access');
    useAuthStore.setState({ status: 'authenticated', user });
    fetchMock.mockRejectedValue(new Error('network down'));

    await logout();

    expect(getAccessToken()).toBeNull();
    expect(useAuthStore.getState()).toMatchObject({ status: 'anonymous', user: null });
  });
});

describe('secret handling', () => {
  it('does not persist the access token in localStorage', async () => {
    fetchMock.mockResolvedValueOnce(json(token)).mockResolvedValueOnce(json(user));
    await login('ada@example.com', 'password');

    expect('access_token' in localStorage).toBe(false);
    expect('refresh_token' in localStorage).toBe(false);
  });
});
