import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  ApiError,
  apiDownload,
  apiRequest,
  clearAccessToken,
  getAccessToken,
  refreshAccessToken,
  setAccessToken,
  setUnauthorizedHandler,
} from '@/api/client';

const jsonResponse = (
  body: unknown,
  status = 200,
  headers: Record<string, string> = {},
): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });

const fetchMock = (): ReturnType<typeof vi.fn<typeof fetch>> => vi.fn<typeof fetch>();

let fetchSpy: ReturnType<typeof vi.fn<typeof fetch>>;
let unauthorized: ReturnType<typeof vi.fn>;

beforeEach(() => {
  clearAccessToken();
  fetchSpy = fetchMock();
  vi.stubGlobal('fetch', fetchSpy);
  unauthorized = vi.fn();
  setUnauthorizedHandler(unauthorized);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  clearAccessToken();
});

describe('apiRequest', () => {
  it('joins the base URL and sends JSON with a correlation ID', async () => {
    fetchSpy.mockResolvedValue(jsonResponse({ ok: true }));

    const result = await apiRequest<{ ok: boolean }>('/api/v1/accounts');

    expect(result).toEqual({ ok: true });
    const [url, init] = fetchSpy.mock.calls[0]!;
    expect(url).toBe('http://localhost:8000/api/v1/accounts');
    const headers = init?.headers as Record<string, string>;
    expect(headers['X-Request-ID']).toMatch(/.+/);
    expect(init?.credentials).toBe('include');
  });

  it('serialises query parameters and skips empty values', async () => {
    fetchSpy.mockResolvedValue(jsonResponse({ items: [] }));

    await apiRequest('/api/v1/transactions', {
      query: { limit: 50, offset: 0, account_id: undefined, date_from: '2026-01-01' },
    });

    const [url] = fetchSpy.mock.calls[0]!;
    expect(url).toContain('limit=50');
    expect(url).toContain('offset=0');
    expect(url).toContain('date_from=2026-01-01');
    expect(url).not.toContain('account_id');
  });

  it('sends a JSON body and method', async () => {
    fetchSpy.mockResolvedValue(jsonResponse({ id: '1' }, 201));

    await apiRequest('/api/v1/accounts', {
      method: 'POST',
      body: { name: 'Current' },
    });

    const [, init] = fetchSpy.mock.calls[0]!;
    expect(init?.method).toBe('POST');
    expect(init?.body).toBe(JSON.stringify({ name: 'Current' }));
    const headers = init?.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
  });

  it('attaches the access token when present', async () => {
    setAccessToken('token-123');
    fetchSpy.mockResolvedValue(jsonResponse({ ok: true }));

    await apiRequest('/api/v1/auth/me');

    const [, init] = fetchSpy.mock.calls[0]!;
    const headers = init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer token-123');
  });

  it('returns undefined for a 204 response', async () => {
    fetchSpy.mockResolvedValue(new Response(null, { status: 204 }));

    await expect(
      apiRequest('/api/v1/transactions/1', { method: 'DELETE' }),
    ).resolves.toBeUndefined();
  });

  it('turns a string error detail into ApiError', async () => {
    fetchSpy.mockResolvedValue(jsonResponse({ detail: 'Account not found' }, 404));

    await expect(apiRequest('/api/v1/accounts/nope')).rejects.toMatchObject({
      status: 404,
      message: 'Account not found',
    });
  });

  it('flattens FastAPI validation errors', async () => {
    fetchSpy.mockResolvedValue(
      jsonResponse(
        {
          detail: [
            { loc: ['body', 'amount'], msg: 'Input should be greater than 0' },
            { loc: ['body', 'currency'], msg: 'Unsupported currency' },
          ],
        },
        422,
      ),
    );

    const error = await apiRequest('/api/v1/transactions', { method: 'POST', body: {} }).catch(
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toContain('amount: Input should be greater than 0');
    expect((error as ApiError).message).toContain('currency: Unsupported currency');
  });

  it('preserves structured import row errors', async () => {
    fetchSpy.mockResolvedValue(
      jsonResponse(
        {
          detail: '2 row(s) failed validation; nothing was imported',
          error_count: 2,
          errors: [
            { row: 2, message: 'Bad date' },
            { row: 3, message: 'Bad amount' },
          ],
        },
        422,
      ),
    );

    const error = (await apiRequest('/api/v1/transactions/import', {
      method: 'POST',
      body: {},
    }).catch((caught: unknown) => caught)) as ApiError;

    expect(error.errors).toEqual([
      { row: 2, message: 'Bad date' },
      { row: 3, message: 'Bad amount' },
    ]);
    expect(error.errorCount).toBe(2);
  });

  it('refreshes once on a 401 and retries the original request', async () => {
    fetchSpy
      .mockResolvedValueOnce(jsonResponse({ detail: 'expired' }, 401))
      .mockResolvedValueOnce(
        jsonResponse({ access_token: 'fresh-token', token_type: 'bearer', expires_in: 900 }),
      )
      .mockResolvedValueOnce(jsonResponse({ id: 'me' }));

    const result = await apiRequest<{ id: string }>('/api/v1/auth/me');

    expect(result).toEqual({ id: 'me' });
    expect(getAccessToken()).toBe('fresh-token');
    const refreshCall = fetchSpy.mock.calls[1]!;
    expect(refreshCall[0]).toBe('http://localhost:8000/api/v1/auth/refresh');
    expect(refreshCall[1]?.credentials).toBe('include');
    const retryHeaders = fetchSpy.mock.calls[2]![1]?.headers as Record<string, string>;
    expect(retryHeaders.Authorization).toBe('Bearer fresh-token');
  });

  it('clears the session and notifies on a failed refresh', async () => {
    setAccessToken('stale');
    fetchSpy
      .mockResolvedValueOnce(jsonResponse({ detail: 'expired' }, 401))
      .mockResolvedValueOnce(jsonResponse({ detail: 'nope' }, 401));

    await expect(apiRequest('/api/v1/auth/me')).rejects.toMatchObject({ status: 401 });

    expect(getAccessToken()).toBeNull();
    expect(unauthorized).toHaveBeenCalledTimes(1);
  });

  it('does not refresh when auth is explicitly disabled', async () => {
    fetchSpy.mockResolvedValue(jsonResponse({ detail: 'bad credentials' }, 401));

    await expect(
      apiRequest('/api/v1/auth/login', { method: 'POST', body: {}, auth: false }),
    ).rejects.toMatchObject({ status: 401 });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(unauthorized).not.toHaveBeenCalled();
  });
});

describe('refreshAccessToken', () => {
  it('stores the refreshed token', async () => {
    fetchSpy.mockResolvedValue(
      jsonResponse({ access_token: 'fresh', token_type: 'bearer', expires_in: 900 }),
    );

    await expect(refreshAccessToken()).resolves.toBe('fresh');
    expect(getAccessToken()).toBe('fresh');
  });

  it('returns null and clears the token when refresh fails', async () => {
    setAccessToken('old');
    fetchSpy.mockResolvedValue(jsonResponse({ detail: 'expired' }, 401));

    await expect(refreshAccessToken()).resolves.toBeNull();
    expect(getAccessToken()).toBeNull();
  });

  it('de-duplicates concurrent refreshes', async () => {
    fetchSpy.mockResolvedValue(
      jsonResponse({ access_token: 'fresh', token_type: 'bearer', expires_in: 900 }),
    );

    const [first, second] = await Promise.all([refreshAccessToken(), refreshAccessToken()]);

    expect(first).toBe('fresh');
    expect(second).toBe('fresh');
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });
});

describe('apiDownload', () => {
  it('returns the blob and filename from Content-Disposition', async () => {
    fetchSpy.mockResolvedValue(
      new Response('date,amount\n2026-01-01,10\n', {
        status: 200,
        headers: {
          'Content-Type': 'text/csv',
          'Content-Disposition': 'attachment; filename="transactions.csv"',
        },
      }),
    );

    const result = await apiDownload('/api/v1/reports/transactions.csv');

    expect(result.filename).toBe('transactions.csv');
    expect(result.blob.size).toBeGreaterThan(0);
  });

  it('falls back to a supplied filename', async () => {
    fetchSpy.mockResolvedValue(new Response('{}', { status: 200 }));

    const result = await apiDownload('/api/v1/export', { fallbackFilename: 'export.json' });

    expect(result.filename).toBe('export.json');
  });
});
