import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { InvestmentsPage } from '@/pages/InvestmentsPage';
import {
  account,
  installApi,
  investmentAccount,
  jsonResponse,
  noContentResponse,
  page,
} from './helpers/api';
import { renderWithProviders } from './helpers/render';

const investment = {
  id: 'inv-1',
  account_id: investmentAccount.id,
  name: '24% Naira Deposit',
  investment_type: 'fixed_rate' as const,
  principal_minor: 1_000_000_000,
  currency: 'GBP',
  rate: '24',
  rate_period: 'annual' as const,
  compounding: 'simple' as const,
  start_date: '2026-01-01',
  maturity_date: null,
  notes: null,
  is_archived: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const returns = {
  investment_id: investment.id,
  name: investment.name,
  currency: 'GBP',
  as_of: '2026-02-01',
  principal_minor: 1_000_000_000,
  value_minor: 1_020_000_000,
  value_source: 'accrual' as const,
  valuation_as_of: null,
  accrued_interest_minor: 20_000_000,
  gain_minor: 20_000_000,
  gain_percent: '2.00',
  projected_monthly_interest_minor: 20_000_000,
  projected_annual_interest_minor: 240_000_000,
  start_date: '2026-01-01',
  maturity_date: null,
};

const valuation = {
  id: 'val-1',
  investment_id: investment.id,
  as_of: '2026-02-01',
  value_minor: 1_050_000_000,
  source: 'manual',
  notes: 'Statement',
  created_at: '2026-02-01T00:00:00Z',
};

const routes = [
  { method: 'GET', path: '/api/v1/investments', response: jsonResponse(page([investment])) },
  {
    method: 'GET',
    path: '/api/v1/accounts',
    response: jsonResponse(page([account, investmentAccount])),
  },
  {
    method: 'GET',
    path: `/api/v1/investments/${investment.id}/returns`,
    response: jsonResponse(returns),
  },
  {
    method: 'GET',
    path: `/api/v1/investments/${investment.id}/valuations`,
    response: jsonResponse(page([valuation])),
  },
  {
    method: 'POST',
    path: '/api/v1/investments',
    response: jsonResponse({ ...investment, id: 'inv-new' }, 201),
  },
  {
    method: 'PATCH',
    path: `/api/v1/investments/${investment.id}`,
    response: jsonResponse({ ...investment, name: 'Updated deposit' }),
  },
  { method: 'DELETE', path: `/api/v1/investments/${investment.id}`, response: noContentResponse() },
  {
    method: 'POST',
    path: `/api/v1/investments/${investment.id}/valuations`,
    response: jsonResponse({ ...valuation, id: 'val-2' }, 201),
  },
  {
    method: 'DELETE',
    path: `/api/v1/investments/${investment.id}/valuations/${valuation.id}`,
    response: noContentResponse(),
  },
] as const;

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>;

beforeEach(() => {
  fetchMock = installApi(routes);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('InvestmentsPage', () => {
  it('lists holdings with values, gains and basis', async () => {
    renderWithProviders(<InvestmentsPage />);

    expect(await screen.findByText('24% Naira Deposit')).toBeInTheDocument();
    expect(await screen.findByText('24% p.a.')).toBeInTheDocument();
    expect(await screen.findByText('Accrued')).toBeInTheDocument();
    expect(screen.getByText(/2\.00%/)).toBeInTheDocument();
  });

  it('creates a fixed-rate investment', async () => {
    renderWithProviders(<InvestmentsPage />);
    await screen.findByText('24% Naira Deposit');
    await userEvent.click(screen.getByRole('button', { name: /new investment/i }));

    const dialog = await screen.findByRole('dialog', { name: /new investment/i });
    await userEvent.type(within(dialog).getByLabelText('Name'), '12% Bond');
    await userEvent.type(within(dialog).getByLabelText(/principal/i), '1000.00');
    await userEvent.type(within(dialog).getByLabelText(/^rate \(%\)$/i), '12');
    await userEvent.click(within(dialog).getByRole('button', { name: /create investment/i }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({
      account_id: investmentAccount.id,
      name: '12% Bond',
      investment_type: 'fixed_rate',
      principal: '1000.00',
      currency: 'GBP',
      rate: '12',
      rate_period: 'annual',
      compounding: 'simple',
    });
  });

  it('validates the name, principal and rate', async () => {
    renderWithProviders(<InvestmentsPage />);
    await screen.findByText('24% Naira Deposit');
    await userEvent.click(screen.getByRole('button', { name: /new investment/i }));
    const dialog = await screen.findByRole('dialog', { name: /new investment/i });
    await userEvent.click(within(dialog).getByRole('button', { name: /create investment/i }));

    expect(await within(dialog).findByText(/enter a name/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/valid principal/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/positive rate/i)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
  });

  it('edits a holding', async () => {
    renderWithProviders(<InvestmentsPage />);
    await screen.findByText('24% Naira Deposit');
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }));
    const dialog = await screen.findByRole('dialog', { name: /edit investment/i });
    await userEvent.clear(within(dialog).getByLabelText('Name'));
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Updated deposit');
    await userEvent.click(within(dialog).getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH');
      expect(JSON.parse(String(patch?.[1]?.body))).toMatchObject({ name: 'Updated deposit' });
    });
  });

  it('opens detail, adds a valuation and lists history', async () => {
    renderWithProviders(<InvestmentsPage />);
    await screen.findByText('24% Naira Deposit');
    await userEvent.click(screen.getByRole('button', { name: 'View' }));

    const dialog = await screen.findByRole('dialog', { name: '24% Naira Deposit' });
    expect(await within(dialog).findByText('£10,200,000.00')).toBeInTheDocument();
    expect(within(dialog).getByText('Statement')).toBeInTheDocument();

    const valueInput = within(dialog).getByLabelText('Value');
    await userEvent.type(valueInput, '10500.00');
    await userEvent.click(within(dialog).getByRole('button', { name: /add valuation/i }));

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(([input, init]) => {
        const url = typeof input === 'string' ? input : input.toString();
        return init?.method === 'POST' && url.endsWith('/valuations');
      });
      expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({ value: '10500.00' });
    });
  });

  it('deletes a valuation', async () => {
    renderWithProviders(<InvestmentsPage />);
    await screen.findByText('24% Naira Deposit');
    await userEvent.click(screen.getByRole('button', { name: 'View' }));
    const dialog = await screen.findByRole('dialog', { name: '24% Naira Deposit' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));
    const confirm = await screen.findByRole('dialog', { name: /delete valuation/i });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Delete' }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(true),
    );
  });

  it('archives a holding', async () => {
    renderWithProviders(<InvestmentsPage />);
    await screen.findByText('24% Naira Deposit');
    await userEvent.click(screen.getByRole('button', { name: 'Archive' }));

    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH');
      expect(JSON.parse(String(patch?.[1]?.body))).toMatchObject({ is_archived: true });
    });
  });

  it('deletes a holding after confirmation', async () => {
    renderWithProviders(<InvestmentsPage />);
    await screen.findByText('24% Naira Deposit');
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
    const confirm = await screen.findByRole('dialog', { name: /delete investment/i });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Delete' }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(true),
    );
  });

  it('shows an empty state', async () => {
    installApi([
      ...routes,
      { method: 'GET', path: '/api/v1/investments', response: jsonResponse(page([])) },
    ]);
    renderWithProviders(<InvestmentsPage />);

    expect(await screen.findByText(/no investments yet/i)).toBeInTheDocument();
  });

  it('surfaces a load error', async () => {
    installApi([
      ...routes,
      {
        method: 'GET',
        path: '/api/v1/investments',
        response: jsonResponse({ detail: 'Boom' }, 500),
      },
    ]);
    renderWithProviders(<InvestmentsPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Boom');
  });
});

describe('InvestmentsPage branches', () => {
  it('creates a market-priced holding without rate fields', async () => {
    renderWithProviders(<InvestmentsPage />);
    await screen.findByText('24% Naira Deposit');
    await userEvent.click(screen.getByRole('button', { name: /new investment/i }));
    const dialog = await screen.findByRole('dialog', { name: /new investment/i });
    await userEvent.selectOptions(within(dialog).getByLabelText('Type'), 'market_priced');
    expect(within(dialog).queryByLabelText(/^rate \(%\)$/i)).not.toBeInTheDocument();
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Index Fund');
    await userEvent.type(within(dialog).getByLabelText(/principal/i), '5000.00');
    await userEvent.click(within(dialog).getByRole('button', { name: /create investment/i }));

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
      expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({
        investment_type: 'market_priced',
        name: 'Index Fund',
      });
    });
  });

  it('validates maturity before the start date', async () => {
    renderWithProviders(<InvestmentsPage />);
    await screen.findByText('24% Naira Deposit');
    await userEvent.click(screen.getByRole('button', { name: /new investment/i }));
    const dialog = await screen.findByRole('dialog', { name: /new investment/i });
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Backwards');
    await userEvent.type(within(dialog).getByLabelText(/principal/i), '100.00');
    await userEvent.type(within(dialog).getByLabelText(/^rate \(%\)$/i), '5');
    await userEvent.clear(within(dialog).getByLabelText(/start date/i));
    await userEvent.type(within(dialog).getByLabelText(/start date/i), '2026-06-01');
    await userEvent.type(within(dialog).getByLabelText(/maturity date/i), '2026-01-01');
    await userEvent.click(within(dialog).getByRole('button', { name: /create investment/i }));

    expect(await within(dialog).findByText(/maturity cannot be before/i)).toBeInTheDocument();
  });

  it('opens the edit form from the detail view', async () => {
    renderWithProviders(<InvestmentsPage />);
    await screen.findByText('24% Naira Deposit');
    await userEvent.click(screen.getByRole('button', { name: 'View' }));
    const detail = await screen.findByRole('dialog', { name: '24% Naira Deposit' });
    await userEvent.click(within(detail).getByRole('button', { name: /edit investment/i }));

    expect(await screen.findByRole('dialog', { name: /edit investment/i })).toBeInTheDocument();
  });

  it('shows an empty valuation history', async () => {
    installApi([
      ...routes,
      {
        method: 'GET',
        path: `/api/v1/investments/${investment.id}/valuations`,
        response: jsonResponse(page([])),
      },
    ]);
    renderWithProviders(<InvestmentsPage />);
    await screen.findByText('24% Naira Deposit');
    await userEvent.click(screen.getByRole('button', { name: 'View' }));
    const dialog = await screen.findByRole('dialog', { name: '24% Naira Deposit' });

    expect(await within(dialog).findByText(/no snapshots/i)).toBeInTheDocument();
  });

  it('cancels a valuation delete', async () => {
    renderWithProviders(<InvestmentsPage />);
    await screen.findByText('24% Naira Deposit');
    await userEvent.click(screen.getByRole('button', { name: 'View' }));
    const detail = await screen.findByRole('dialog', { name: '24% Naira Deposit' });
    await userEvent.click(within(detail).getByRole('button', { name: 'Delete' }));
    const confirm = await screen.findByRole('dialog', { name: /delete valuation/i });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog', { name: /delete valuation/i })).not.toBeInTheDocument();
  });
});
