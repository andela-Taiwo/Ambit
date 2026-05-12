import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ReportsPage } from '@/pages/ReportsPage';
import { installApi, jsonResponse } from './helpers/api';
import { renderWithProviders } from './helpers/render';

const netWorth = {
  as_of: '2026-02-01',
  base_currency: 'GBP',
  total_minor: 741_000,
  accounts_total_minor: 130_000,
  investments_total_minor: 611_000,
  accounts: [
    {
      account_id: 'account-1',
      name: 'Current Account',
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
        amount_minor: 611_000,
        base_currency: 'GBP',
        base_minor: 611_000,
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

const history = {
  base_currency: 'GBP',
  points: [
    {
      as_of: '2026-01-31',
      total_minor: 700_000,
      accounts_minor: 120_000,
      investments_minor: 580_000,
    },
    {
      as_of: '2026-02-28',
      total_minor: 741_000,
      accounts_minor: 130_000,
      investments_minor: 611_000,
    },
  ],
};

const cashFlow = {
  base_currency: 'GBP',
  date_from: '2026-01-01',
  date_to: '2026-02-28',
  interval: 'month',
  items: [
    {
      period_start: '2026-01-01',
      period_end: '2026-02-01',
      income_minor: 50_000,
      expense_minor: 20_000,
      net_minor: 30_000,
      transaction_count: 2,
    },
    {
      period_start: '2026-02-01',
      period_end: '2026-03-01',
      income_minor: 0,
      expense_minor: 10_000,
      net_minor: -10_000,
      transaction_count: 1,
    },
  ],
};

const breakdown = {
  base_currency: 'GBP',
  date_from: '2026-01-01',
  date_to: '2026-02-28',
  kind: 'expense',
  include_subcategories: true,
  total_minor: 30_000,
  items: [
    {
      category_id: 'cat-groceries',
      name: 'Groceries',
      parent_id: null,
      total_minor: 30_000,
      transaction_count: 2,
      percent_of_total: '100.00',
    },
  ],
};

const routes = [
  { method: 'GET', path: '/api/v1/reports/net-worth', response: jsonResponse(netWorth) },
  { method: 'GET', path: '/api/v1/reports/net-worth/history', response: jsonResponse(history) },
  { method: 'GET', path: '/api/v1/reports/cash-flow', response: jsonResponse(cashFlow) },
  { method: 'GET', path: '/api/v1/reports/category-breakdown', response: jsonResponse(breakdown) },
  {
    method: 'GET',
    path: '/api/v1/reports/transactions.csv',
    response: new Response('date,amount\n2026-01-01,10\n', {
      status: 200,
      headers: {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename="transactions.csv"',
      },
    }),
  },
] as const;

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>;

beforeEach(() => {
  fetchMock = installApi(routes);
  Object.defineProperty(URL, 'createObjectURL', {
    value: vi.fn(() => 'blob:transactions'),
    configurable: true,
  });
  Object.defineProperty(URL, 'revokeObjectURL', { value: vi.fn(), configurable: true });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('ReportsPage', () => {
  it('renders net worth, history, cash flow and category breakdown', async () => {
    renderWithProviders(<ReportsPage />);

    expect((await screen.findAllByText('£7,410.00')).length).toBeGreaterThan(0);
    expect(screen.getByRole('img', { name: 'Net worth history' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Monthly net cash flow' })).toBeInTheDocument();
    expect(screen.getAllByText('£300.00').length).toBeGreaterThan(0);
    expect(screen.getByText(/100\.00%/)).toBeInTheDocument();
    expect(screen.getByText('Groceries')).toBeInTheDocument();
    expect(screen.getByText('Bond')).toBeInTheDocument();
  });

  it('downloads the CSV export', async () => {
    renderWithProviders(<ReportsPage />);
    await screen.findAllByText('£7,410.00');

    await userEvent.click(screen.getByRole('button', { name: /download transactions csv/i }));

    expect(await screen.findByText(/downloaded transactions\.csv/i)).toBeInTheDocument();
    const csvCall = fetchMock.mock.calls.find(([input]) =>
      (typeof input === 'string' ? input : input.toString()).includes('/reports/transactions.csv'),
    );
    expect(csvCall).toBeDefined();
    expect(URL.createObjectURL).toHaveBeenCalled();
  });

  it('switches the breakdown to income', async () => {
    renderWithProviders(<ReportsPage />);
    await screen.findAllByText('£7,410.00');
    await userEvent.selectOptions(screen.getByLabelText('Kind'), 'income');

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map(([input]) =>
        typeof input === 'string' ? input : input.toString(),
      );
      expect(urls.some((url) => url.includes('kind=income'))).toBe(true);
    });
  });

  it('surfaces a missing-rate error', async () => {
    installApi([
      ...routes,
      {
        method: 'GET',
        path: '/api/v1/reports/net-worth',
        response: jsonResponse({ detail: 'No exchange rate from NGN to GBP' }, 422),
      },
    ]);
    renderWithProviders(<ReportsPage />);

    const alerts = await screen.findAllByRole('alert');
    expect(alerts.some((alert) => /no exchange rate/i.test(alert.textContent ?? ''))).toBe(true);
  });
});

describe('ReportsPage branches', () => {
  it('shows empty cash-flow and breakdown states', async () => {
    installApi([
      ...routes,
      {
        method: 'GET',
        path: '/api/v1/reports/cash-flow',
        response: jsonResponse({ ...cashFlow, items: [] }),
      },
      {
        method: 'GET',
        path: '/api/v1/reports/category-breakdown',
        response: jsonResponse({ ...breakdown, items: [], total_minor: 0 }),
      },
    ]);
    renderWithProviders(<ReportsPage />);

    expect(await screen.findByText(/no cash flow in this range/i)).toBeInTheDocument();
    expect(await screen.findByText(/no transactions in this range/i)).toBeInTheDocument();
  });

  it('changes the reporting dates', async () => {
    const localFetch = installApi(routes);
    renderWithProviders(<ReportsPage />);
    await screen.findAllByText('£7,410.00');

    const dateInputs = screen.getAllByDisplayValue(/\d{4}-\d{2}-\d{2}/);
    await userEvent.clear(dateInputs[0]!);
    await userEvent.type(dateInputs[0]!, '2025-01-01');

    await waitFor(() => {
      const urls = localFetch.mock.calls.map(([input]) =>
        typeof input === 'string' ? input : input.toString(),
      );
      expect(urls.some((url) => url.includes('date_from=2025-01-01'))).toBe(true);
    });
  });

  it('surfaces a download error', async () => {
    installApi([
      ...routes,
      {
        method: 'GET',
        path: '/api/v1/reports/transactions.csv',
        response: jsonResponse({ detail: 'Export failed' }, 500),
      },
    ]);
    renderWithProviders(<ReportsPage />);
    await screen.findAllByText('£7,410.00');
    await userEvent.click(screen.getByRole('button', { name: /download transactions csv/i }));

    expect(await screen.findByText('Export failed')).toBeInTheDocument();
  });
});
