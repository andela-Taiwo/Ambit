import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { listAccounts, listBudgets, listTransactions } from '@/api/endpoints';
import { clearAccessToken } from '@/api/client';

const json = (body: unknown): Response =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>;

beforeEach(() => {
  clearAccessToken();
  fetchMock = vi
    .fn<typeof fetch>()
    .mockResolvedValue(json({ items: [], total: 0, limit: 100, offset: 0 }));
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('list endpoints respect backend query caps', () => {
  it('requests accounts with a limit of at most 100', async () => {
    await listAccounts();
    const url = new URL(String(fetchMock.mock.calls[0]?.[0]));
    expect(url.searchParams.get('limit')).toBe('100');
  });

  it('requests transactions with paging defaults', async () => {
    await listTransactions();
    const url = new URL(String(fetchMock.mock.calls[0]?.[0]));
    expect(url.searchParams.get('limit')).toBe('50');
    expect(url.searchParams.get('offset')).toBe('0');
  });

  it('requests budgets including archived when asked', async () => {
    await listBudgets(true);
    const url = new URL(String(fetchMock.mock.calls[0]?.[0]));
    expect(url.searchParams.get('include_archived')).toBe('true');
  });
});
