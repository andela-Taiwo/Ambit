import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError, fetchHealth } from '@/api/health';

const okResponse = (body: unknown): Response =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('fetchHealth', () => {
  it('returns the parsed health payload', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okResponse({ status: 'ok' })));

    await expect(fetchHealth('https://api.example.com')).resolves.toEqual({ status: 'ok' });
  });

  it('calls the /health endpoint on the configured base URL', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(okResponse({ status: 'ok' }));
    vi.stubGlobal('fetch', fetchMock);

    await fetchHealth('https://api.example.com');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe('https://api.example.com/health');
  });

  it('sends a correlation ID so requests are traceable end to end', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(okResponse({ status: 'ok' }));
    vi.stubGlobal('fetch', fetchMock);

    await fetchHealth('https://api.example.com');

    const init = fetchMock.mock.calls[0]?.[1];
    const headers = init?.headers as Record<string, string>;
    expect(headers['X-Request-ID']).toMatch(/.+/);
  });

  it('raises ApiError on a non-2xx response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('nope', { status: 503 })));

    await expect(fetchHealth('https://api.example.com')).rejects.toBeInstanceOf(ApiError);
  });

  it('raises ApiError when the payload does not match the contract', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okResponse({ unexpected: true })));

    await expect(fetchHealth('https://api.example.com')).rejects.toBeInstanceOf(ApiError);
  });
});
