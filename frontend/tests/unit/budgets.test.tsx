import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { addMonthsToMonth, currentMonth } from '@/lib/dates';
import { BudgetsPage } from '@/pages/BudgetsPage';
import { categories, installApi, jsonResponse, noContentResponse, page } from './helpers/api';
import { renderWithProviders } from './helpers/render';

const budget = {
  id: 'budget-1',
  category_id: 'cat-groceries',
  amount_minor: 30_000,
  currency: 'GBP',
  starts_on: '2026-01-01',
  ends_on: null,
  rollover_enabled: true,
  is_archived: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const status = {
  period_start: `${currentMonth()}-01`,
  period_end: `${addMonthsToMonth(currentMonth(), 1)}-01`,
  base_currency: 'GBP',
  items: [
    {
      budget_id: budget.id,
      category_id: budget.category_id,
      currency: 'GBP',
      period_start: `${currentMonth()}-01`,
      period_end: `${addMonthsToMonth(currentMonth(), 1)}-01`,
      limit_minor: 30_000,
      rollover_in_minor: 5_000,
      effective_limit_minor: 35_000,
      spent_minor: 12_000,
      remaining_minor: 23_000,
      carry_forward_minor: 23_000,
      percent_used: '34.29',
      status: 'on_track',
      transaction_count: 2,
    },
  ],
};

const routes = [
  { method: 'GET', path: '/api/v1/budgets/status', response: jsonResponse(status) },
  { method: 'GET', path: '/api/v1/budgets', response: jsonResponse(page([budget])) },
  { method: 'GET', path: '/api/v1/categories', response: jsonResponse(page(categories)) },
  {
    method: 'POST',
    path: '/api/v1/budgets',
    response: jsonResponse({ ...budget, id: 'budget-new' }, 201),
  },
  {
    method: 'PATCH',
    path: `/api/v1/budgets/${budget.id}`,
    response: jsonResponse({ ...budget, amount_minor: 40_000 }),
  },
  { method: 'DELETE', path: `/api/v1/budgets/${budget.id}`, response: noContentResponse() },
] as const;

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>;

beforeEach(() => {
  fetchMock = installApi(routes);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('BudgetsPage', () => {
  it('shows budget-vs-actual with rollover', async () => {
    renderWithProviders(<BudgetsPage />);

    expect(await screen.findByText('Groceries')).toBeInTheDocument();
    expect(screen.getByText(/£120\.00 of £350\.00/)).toBeInTheDocument();
    expect(screen.getByText(/£120\.00 of £350\.00 · 34\.29%/)).toBeInTheDocument();
    expect(screen.getByText('Rollover in')).toBeInTheDocument();
    expect(screen.getByText('£50.00')).toBeInTheDocument();
    expect(screen.getAllByText('£230.00').length).toBeGreaterThan(0);
  });

  it('creates a budget', async () => {
    renderWithProviders(<BudgetsPage />);
    await screen.findByText('Groceries');
    await userEvent.click(screen.getByRole('button', { name: /new budget/i }));

    const dialog = await screen.findByRole('dialog', { name: /new budget/i });
    await userEvent.selectOptions(within(dialog).getByLabelText('Category'), 'cat-groceries');
    await userEvent.type(within(dialog).getByLabelText(/monthly limit/i), '300.00');
    await userEvent.click(within(dialog).getByRole('button', { name: /create budget/i }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({
      category_id: 'cat-groceries',
      amount: '300.00',
      currency: 'GBP',
      rollover_enabled: false,
    });
  });

  it('rejects an invalid limit', async () => {
    renderWithProviders(<BudgetsPage />);
    await screen.findByText('Groceries');
    await userEvent.click(screen.getByRole('button', { name: /new budget/i }));
    const dialog = await screen.findByRole('dialog', { name: /new budget/i });
    await userEvent.selectOptions(within(dialog).getByLabelText('Category'), 'cat-groceries');
    await userEvent.type(within(dialog).getByLabelText(/monthly limit/i), '10.005');
    await userEvent.click(within(dialog).getByRole('button', { name: /create budget/i }));

    expect(await within(dialog).findByText(/valid limit/i)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
  });

  it('edits amount and rollover', async () => {
    renderWithProviders(<BudgetsPage />);
    await screen.findByText('Groceries');
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }));
    const dialog = await screen.findByRole('dialog', { name: /edit budget/i });
    await userEvent.clear(within(dialog).getByLabelText(/monthly limit/i));
    await userEvent.type(within(dialog).getByLabelText(/monthly limit/i), '400.00');
    await userEvent.click(within(dialog).getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH');
      expect(JSON.parse(String(patch?.[1]?.body))).toMatchObject({
        amount: '400.00',
        rollover_enabled: true,
      });
    });
  });

  it('moves to the next month', async () => {
    renderWithProviders(<BudgetsPage />);
    await screen.findByText('Groceries');
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map(([input]) =>
        typeof input === 'string' ? input : input.toString(),
      );
      expect(
        urls.some((url) => url.includes(`period=${addMonthsToMonth(currentMonth(), 1)}`)),
      ).toBe(true);
    });
  });

  it('deletes a budget after confirmation', async () => {
    renderWithProviders(<BudgetsPage />);
    await screen.findByText('Groceries');
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('dialog', { name: /delete budget/i });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(true),
    );
  });

  it('shows an empty state', async () => {
    installApi([
      ...routes,
      {
        method: 'GET',
        path: '/api/v1/budgets/status',
        response: jsonResponse({ ...status, items: [] }),
      },
      { method: 'GET', path: '/api/v1/budgets', response: jsonResponse(page([])) },
    ]);
    renderWithProviders(<BudgetsPage />);

    expect(await screen.findByText(/no budgets for this month/i)).toBeInTheDocument();
  });

  it('surfaces a missing-rate error', async () => {
    installApi([
      ...routes,
      {
        method: 'GET',
        path: '/api/v1/budgets/status',
        response: jsonResponse({ detail: 'No exchange rate from NGN to GBP' }, 422),
      },
    ]);
    renderWithProviders(<BudgetsPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent(/no exchange rate/i);
  });
});

describe('BudgetsPage branches', () => {
  it('shows mixed currencies instead of summing them', async () => {
    installApi([
      ...routes,
      {
        method: 'GET',
        path: '/api/v1/budgets/status',
        response: jsonResponse({
          ...status,
          items: [
            status.items[0]!,
            { ...status.items[0]!, budget_id: 'budget-2', currency: 'NGN' },
          ],
        }),
      },
    ]);
    renderWithProviders(<BudgetsPage />);

    expect(await screen.findAllByText('Mixed currencies')).toHaveLength(2);
  });

  it('moves between months and returns to this month', async () => {
    const localFetch = installApi(routes);
    renderWithProviders(<BudgetsPage />);
    await screen.findByText('Groceries');

    await userEvent.click(screen.getByRole('button', { name: 'Previous' }));
    await userEvent.click(screen.getByRole('button', { name: 'This month' }));

    await waitFor(() => {
      const urls = localFetch.mock.calls.map(([input]) =>
        typeof input === 'string' ? input : input.toString(),
      );
      expect(urls.some((url) => url.includes(`period=${currentMonth()}`))).toBe(true);
    });
  });

  it('clears an end date and enables rollover', async () => {
    const withEnd = { ...budget, ends_on: '2026-06-01', rollover_enabled: false };
    const localFetch = installApi([
      ...routes,
      { method: 'GET', path: '/api/v1/budgets', response: jsonResponse(page([withEnd])) },
    ]);
    renderWithProviders(<BudgetsPage />);
    await screen.findByText('Groceries');
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }));
    const dialog = await screen.findByRole('dialog', { name: /edit budget/i });
    await userEvent.clear(within(dialog).getByLabelText(/ends on/i));
    await userEvent.click(within(dialog).getByLabelText(/roll unspent/i));
    await userEvent.click(within(dialog).getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      const patch = localFetch.mock.calls.find(([, init]) => init?.method === 'PATCH');
      expect(JSON.parse(String(patch?.[1]?.body))).toMatchObject({
        ends_on: null,
        rollover_enabled: true,
      });
    });
  });

  it('cancels a delete', async () => {
    renderWithProviders(<BudgetsPage />);
    await screen.findByText('Groceries');
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('dialog', { name: /delete budget/i });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
