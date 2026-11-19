/**
 * Authentication state.
 *
 * Access token: memory only. Refresh token: httpOnly cookie, exchanged by
 * `bootstrapAuth()` on page load. Zustand holds only session/UI state; server
 * data still belongs to TanStack Query.
 */

import { create } from 'zustand';

import {
  clearAccessToken,
  refreshAccessToken,
  setAccessToken,
  setUnauthorizedHandler,
} from '@/api/client';
import { loginRequest, logoutRequest, meRequest, registerRequest } from '@/api/endpoints';
import type { RegisterRequest, UserResponse } from '@/api/types';

export type AuthStatus = 'booting' | 'authenticated' | 'anonymous';

interface AuthState {
  status: AuthStatus;
  user: UserResponse | null;
  setUser: (user: UserResponse) => void;
  signOutLocally: () => void;
}

export const useAuthStore = create<AuthState>()((set) => ({
  status: 'booting',
  user: null,
  setUser: (user) => set({ user, status: 'authenticated' }),
  signOutLocally: () => {
    clearAccessToken();
    set({ status: 'anonymous', user: null });
  },
}));

setUnauthorizedHandler(() => {
  useAuthStore.getState().signOutLocally();
});

let bootstrapInFlight: Promise<void> | null = null;

export const bootstrapAuth = async (): Promise<void> => {
  if (bootstrapInFlight !== null) return bootstrapInFlight;

  bootstrapInFlight = (async () => {
    const token = await refreshAccessToken();
    if (token === null) {
      useAuthStore.getState().signOutLocally();
      return;
    }
    try {
      const user = await meRequest();
      useAuthStore.getState().setUser(user);
    } catch {
      useAuthStore.getState().signOutLocally();
    }
  })();

  try {
    await bootstrapInFlight;
  } finally {
    bootstrapInFlight = null;
  }
};

export const login = async (email: string, password: string): Promise<UserResponse> => {
  const token = await loginRequest({ email, password });
  setAccessToken(token.access_token);
  try {
    const user = await meRequest();
    useAuthStore.getState().setUser(user);
    return user;
  } catch (error) {
    useAuthStore.getState().signOutLocally();
    throw error;
  }
};

export const register = async (payload: RegisterRequest): Promise<UserResponse> => {
  await registerRequest(payload);
  return login(payload.email, payload.password);
};

export const logout = async (): Promise<void> => {
  try {
    await logoutRequest();
  } catch {
    // A failed logout must still clear local state; the cookie is best-effort.
  } finally {
    useAuthStore.getState().signOutLocally();
  }
};

/** Test-only: return the singleton to its initial state. */
export const resetAuthForTests = (): void => {
  bootstrapInFlight = null;
  clearAccessToken();
  useAuthStore.setState({ status: 'booting', user: null });
};
