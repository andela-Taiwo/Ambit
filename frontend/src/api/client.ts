/**
 * Typed HTTP client.
 *
 * The access token lives in memory only (never localStorage): an XSS payload
 * cannot read it, and a refresh token lives in an httpOnly cookie. A 401
 * triggers one refresh-and-retry; failure clears the session and notifies the
 * auth store.
 */

import { config } from '@/app/config';
import type { CsvImportRowError, TokenResponse } from '@/api/types';

export interface ApiErrorBody {
  detail?: unknown;
  errors?: CsvImportRowError[];
  error_count?: number;
  [key: string]: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly errors: CsvImportRowError[] | undefined;
  readonly errorCount: number | undefined;
  readonly body: ApiErrorBody | undefined;

  constructor(
    message: string,
    status: number,
    options: { errors?: CsvImportRowError[]; errorCount?: number; body?: ApiErrorBody } = {},
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errors = options.errors;
    this.errorCount = options.errorCount;
    this.body = options.body;
  }
}

export interface QueryValue {
  readonly [key: string]: string | number | boolean | null | undefined;
}

export interface ApiRequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body?: unknown;
  query?: QueryValue;
  signal?: AbortSignal;
  /** Set false for login/register/refresh, where a 401 is a real failure. */
  auth?: boolean;
  /** Internal: prevents a refreshed request from refreshing again. */
  retryOn401?: boolean;
}

let accessToken: string | null = null;
let refreshInFlight: Promise<string | null> | null = null;
let unauthorizedHandler: (() => void) | null = null;

export const getAccessToken = (): string | null => accessToken;
export const setAccessToken = (token: string | null): void => {
  accessToken = token;
};
export const clearAccessToken = (): void => {
  accessToken = null;
};
export const setUnauthorizedHandler = (handler: (() => void) | null): void => {
  unauthorizedHandler = handler;
};

const newRequestId = (): string =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `req-${String(Date.now())}-${Math.random().toString(36).slice(2)}`;

const buildUrl = (path: string, query?: QueryValue): string => {
  const url = new URL(`${config.apiBaseUrl}${path}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === '') continue;
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
};

const parseErrorBody = async (response: Response): Promise<ApiError> => {
  let body: ApiErrorBody | undefined;
  try {
    body = (await response.json()) as ApiErrorBody;
  } catch {
    body = undefined;
  }

  let message = response.statusText || `Request failed with status ${String(response.status)}`;
  if (typeof body?.detail === 'string') {
    message = body.detail;
  } else if (Array.isArray(body?.detail)) {
    const messages = body.detail.map((item) => {
      if (typeof item !== 'object' || item === null) return String(item);
      const record = item as { loc?: unknown; msg?: unknown };
      const location = Array.isArray(record.loc) ? record.loc.slice(1).join('.') : '';
      const text = typeof record.msg === 'string' ? record.msg : 'Invalid value';
      return location === '' ? text : `${location}: ${text}`;
    });
    message = messages.join('; ');
  }

  return new ApiError(message, response.status, {
    ...(body?.errors !== undefined ? { errors: body.errors } : {}),
    ...(body?.error_count !== undefined ? { errorCount: body.error_count } : {}),
    ...(body !== undefined ? { body } : {}),
  });
};

const send = async (
  path: string,
  options: ApiRequestOptions,
  token: string | null,
): Promise<Response> => {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'X-Request-ID': newRequestId(),
  };
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (token !== null) headers.Authorization = `Bearer ${token}`;

  return fetch(buildUrl(path, options.query), {
    method: options.method ?? 'GET',
    headers,
    credentials: 'include',
    ...(options.body !== undefined ? { body: JSON.stringify(options.body) } : {}),
    ...(options.signal !== undefined ? { signal: options.signal } : {}),
  });
};

export const refreshAccessToken = async (): Promise<string | null> => {
  if (refreshInFlight !== null) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      const response = await fetch(`${config.apiBaseUrl}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: { Accept: 'application/json', 'X-Request-ID': newRequestId() },
        credentials: 'include',
      });
      if (!response.ok) {
        clearAccessToken();
        return null;
      }
      const body = (await response.json()) as TokenResponse;
      setAccessToken(body.access_token);
      return body.access_token;
    } catch {
      clearAccessToken();
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
};

export const apiRequest = async <T>(path: string, options: ApiRequestOptions = {}): Promise<T> => {
  const useAuth = options.auth !== false;
  const retryOn401 = options.retryOn401 !== false;
  let token = useAuth ? accessToken : null;
  let response = await send(path, options, token);

  if (response.status === 401 && useAuth && retryOn401) {
    const refreshed = await refreshAccessToken();
    if (refreshed !== null) {
      token = refreshed;
      response = await send(path, { ...options, retryOn401: false }, token);
    } else {
      clearAccessToken();
      unauthorizedHandler?.();
    }
  }

  if (!response.ok) {
    throw await parseErrorBody(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
};

const filenameFromDisposition = (header: string | null, fallback: string): string => {
  if (header === null) return fallback;
  const match = /filename="?([^";]+)"?/.exec(header);
  return match?.[1] ?? fallback;
};

export const apiDownload = async (
  path: string,
  options: { fallbackFilename?: string; query?: QueryValue } = {},
): Promise<{ blob: Blob; filename: string }> => {
  let response = await send(
    path,
    { ...(options.query !== undefined ? { query: options.query } : {}) },
    accessToken,
  );
  if (response.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed !== null) {
      response = await send(
        path,
        { ...(options.query !== undefined ? { query: options.query } : {}) },
        refreshed,
      );
    } else {
      clearAccessToken();
      unauthorizedHandler?.();
    }
  }
  if (!response.ok) {
    throw await parseErrorBody(response);
  }
  return {
    blob: await response.blob(),
    filename: filenameFromDisposition(
      response.headers.get('Content-Disposition'),
      options.fallbackFilename ?? 'download',
    ),
  };
};

export const downloadBlob = (blob: Blob, filename: string): void => {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
};
