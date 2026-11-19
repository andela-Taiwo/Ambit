import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest';

import { DashboardPage } from '@/pages/DashboardPage';
import { account, categories, installApi, jsonResponse, page, transaction } from './helpers/api';
import { renderWithProviders } from './helpers/render';

const netWorth = {
  as_of: '2026-02-01',
  base_currency: 'GBP',
  total_minor: 741_000,
  accounts_total_minor: 130_000,
  investments_total_minor: 611_000,
  accounts: [
    {
      account_id: account.id,
      name: account.name,
      account_type: 'current',
      balance: {
        currency: 'GBP',
        amount_minor: 130_000,
        base_currency: 'GBP',
        base_minor: 130_000,
        rate: '1',
        rate_as_of: '2026-02-01',
        rate_source: 'identity',
        rate_is_inverse: false,
      },
    },
  ],
  investments: [
    {
      investment_id: 'inv-1',
      name: 'Bond',
      investment_type: 'fixed_rate',
      value: {
        currency: 'GBP',
        amount_minor: 101_000,
        base_currency: 'GBP',
        base_minor: 101_000,
        rate: '1',
        rate_as_of: '2026-02-01',
        rate_source: 'identity',
        rate_is_inverse: false,
      },
      value_source: 'accrual',
      valuation_as_of: null,
    },
  ],
};

const budgetStatus = {
  period_start: '2026-02-01',
  period_end: '2026-03-01',
  base_currency: 'GBP',
  items: [
    {
      budget_id: 'budget-1',
      category_id: 'cat-groceries',
      currency: 'GBP',
      period_start: '2026-02-01',
      period_end: '2026-03-01',
      limit_minor: 30_000,
      rollover_in_minor: 0,
      effective_limit_minor: 30_000,
      spent_minor: 12_000,
      remaining_minor: 18_000,
      carry_forward_minor: 0,
      percent_used: '40.00',
      status: 'on_track',
      transaction_count: 1,
    },
  ],
};

const routes = [
  { method: 'GET', path: '/api/v1/reports/net-worth', response: jsonResponse(netWorth) },
  { method: 'GET', path: '/api/v1/budgets/status', response: jsonResponse(budgetStatus) },
  { method: 'GET', path: '/api/v1/transactions', response: jsonResponse(page([transaction])) },
  { method: 'GET', path: '/api/v1/accounts', response: jsonResponse(page([account])) },
  { method: 'GET', path: '/api/v1/categories', response: jsonResponse(page(categories)) },
] as const;

beforeEach(() => {
  installApi(routes);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('DashboardPage', () => {
  it('shows net worth, budget health and recent activity', async () => {
    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText('£7,410.00')).toBeInTheDocument();
    expect(screen.getByText('£1,300.00')).toBeInTheDocument();
    expect(screen.getByText('£6,110.00')).toBeInTheDocument();
    expect(await screen.findByText('Groceries')).toBeInTheDocument();
    expect(screen.getByText(/£120\.00 of £300\.00 · 40\.00%/)).toBeInTheDocument();
    expect(await screen.findByText('Weekly shop')).toBeInTheDocument();
    expect(screen.getByText(/Current Account/)).toBeInTheDocument();
  });

  it('offers quick links to the main workflows', async () => {
    renderWithProviders(<DashboardPage />);

    expect(await screen.findByRole('link', { name: /add a transaction/i })).toHaveAttribute(
      'href',
      '/transactions',
    );
    expect(screen.getByRole('link', { name: /view reports/i })).toHaveAttribute('href', '/reports');
  });

  it('shows empty states before data exists', async () => {
    installApi([
      {
        method: 'GET',
        path: '/api/v1/reports/net-worth',
        response: jsonResponse({ ...netWorth, total_minor: 0, accounts: [], investments: [] }),
      },
      {
        method: 'GET',
        path: '/api/v1/budgets/status',
        response: jsonResponse({ ...budgetStatus, items: [] }),
      },
      { method: 'GET', path: '/api/v1/transactions', response: jsonResponse(page([])) },
      { method: 'GET', path: '/api/v1/accounts', response: jsonResponse(page([])) },
      { method: 'GET', path: '/api/v1/categories', response: jsonResponse(page([])) },
    ]);

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText(/no budgets yet/i)).toBeInTheDocument();
    expect(await screen.findByText(/nothing recorded yet/i)).toBeInTheDocument();
  });

  it('surfaces a net-worth error such as a missing rate', async () => {
    installApi([
      {
        method: 'GET',
        path: '/api/v1/reports/net-worth',
        response: jsonResponse({ detail: 'No exchange rate from NGN to GBP' }, 422),
      },
      {
        method: 'GET',
        path: '/api/v1/budgets/status',
        response: jsonResponse({ ...budgetStatus, items: [] }),
      },
      { method: 'GET', path: '/api/v1/transactions', response: jsonResponse(page([])) },
      { method: 'GET', path: '/api/v1/accounts', response: jsonResponse(page([])) },
      { method: 'GET', path: '/api/v1/categories', response: jsonResponse(page([])) },
    ]);

    renderWithProviders(<DashboardPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent(/no exchange rate/i);
  });
});
