import { vi } from 'vitest';

export const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

export const noContentResponse = (): Response => new Response(null, { status: 204 });

export interface Route {
  method: string;
  path: string;
  response: Response | (() => Response);
}

export const installApi = (routes: readonly Route[]): ReturnType<typeof vi.fn<typeof fetch>> => {
  const fetchMock = vi.fn<typeof fetch>((input, init) => {
    const url = new URL(typeof input === 'string' ? input : input.toString());
    const method = (init?.method ?? 'GET').toUpperCase();
    const route = [...routes]
      .reverse()
      .find((item) => item.method === method && item.path === url.pathname);
    if (route === undefined) {
      return Promise.resolve(
        jsonResponse({ detail: `No mock for ${method} ${url.pathname}` }, 500),
      );
    }
    return Promise.resolve(
      typeof route.response === 'function' ? route.response() : route.response.clone(),
    );
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
};

export const page = <T>(
  items: T[],
  overrides: Partial<{ total: number; limit: number; offset: number }> = {},
): {
  items: T[];
  total: number;
  limit: number;
  offset: number;
} => ({
  items,
  total: overrides.total ?? items.length,
  limit: overrides.limit ?? 50,
  offset: overrides.offset ?? 0,
});

export const user = {
  id: 'user-1',
  email: 'ada@example.com',
  display_name: 'Ada Lovelace',
  base_currency: 'GBP',
};

export const account = {
  id: 'account-1',
  name: 'Current Account',
  account_type: 'current' as const,
  currency: 'GBP',
  opening_balance_minor: 100_000,
  is_archived: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

export const investmentAccount = {
  ...account,
  id: 'account-2',
  name: 'Broker',
  account_type: 'investment' as const,
};

export const categories = [
  {
    id: 'cat-groceries',
    name: 'Groceries',
    kind: 'expense' as const,
    parent_id: null,
    is_archived: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'cat-housing',
    name: 'Housing',
    kind: 'expense' as const,
    parent_id: null,
    is_archived: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'cat-salary',
    name: 'Salary',
    kind: 'income' as const,
    parent_id: null,
    is_archived: false,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

export const transaction = {
  id: 'tx-1',
  account_id: 'account-1',
  category_id: 'cat-groceries',
  transaction_type: 'expense' as const,
  amount_minor: 2_499,
  signed_amount_minor: -2_499,
  currency: 'GBP',
  occurred_on: '2026-01-15',
  description: 'Weekly shop',
  notes: null,
  transfer_group_id: null,
  recurring_rule_id: null,
  occurrence_on: null,
  import_batch_id: null,
  external_id: null,
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
};
