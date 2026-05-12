import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { RecurringPage } from '@/pages/RecurringPage';
import {
  account,
  categories,
  installApi,
  jsonResponse,
  noContentResponse,
  page,
} from './helpers/api';
import { renderWithProviders } from './helpers/render';

const rule = {
  id: 'rule-1',
  account_id: account.id,
  category_id: 'cat-housing',
  description: 'Rent',
  transaction_type: 'expense' as const,
  amount_minor: 100_000,
  currency: 'GBP',
  frequency: 'monthly' as const,
  interval: 1,
  day_of_month: 31,
  starts_on: '2026-01-31',
  ends_on: null,
  next_run_on: '2026-02-28',
  last_run_on: '2026-01-31',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const routes = [
  { method: 'GET', path: '/api/v1/recurring-rules', response: jsonResponse(page([rule])) },
  { method: 'GET', path: '/api/v1/accounts', response: jsonResponse(page([account])) },
  { method: 'GET', path: '/api/v1/categories', response: jsonResponse(page(categories)) },
  {
    method: 'POST',
    path: '/api/v1/recurring-rules',
    response: jsonResponse({ ...rule, id: 'rule-new' }, 201),
  },
  {
    method: 'PATCH',
    path: `/api/v1/recurring-rules/${rule.id}`,
    response: jsonResponse({ ...rule, description: 'Rent (new)' }),
  },
  { method: 'DELETE', path: `/api/v1/recurring-rules/${rule.id}`, response: noContentResponse() },
  {
    method: 'POST',
    path: `/api/v1/recurring-rules/${rule.id}/run`,
    response: jsonResponse({
      rule_id: rule.id,
      generated_count: 2,
      skipped_count: 0,
      last_occurrence_on: '2026-02-28',
      next_run_on: '2026-03-31',
    }),
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

describe('RecurringPage', () => {
  it('lists rules with schedule and status', async () => {
    renderWithProviders(<RecurringPage />);

    expect(await screen.findByText('Rent')).toBeInTheDocument();
    expect(screen.getByText('Monthly · every 1')).toBeInTheDocument();
    expect(screen.getByText('£1,000.00')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('creates a monthly rule', async () => {
    renderWithProviders(<RecurringPage />);
    await screen.findByText('Rent');
    await userEvent.click(screen.getByRole('button', { name: /new recurring rule/i }));

    const dialog = await screen.findByRole('dialog', { name: /new recurring rule/i });
    await userEvent.type(within(dialog).getByLabelText(/amount/i), '1200.00');
    await userEvent.type(within(dialog).getByLabelText('Description'), 'Salary');
    await userEvent.selectOptions(within(dialog).getByLabelText('Type'), 'income');
    await userEvent.selectOptions(within(dialog).getByLabelText('Category'), 'cat-salary');
    await userEvent.click(within(dialog).getByRole('button', { name: /create rule/i }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    const post = fetchMock.mock.calls.find(
      ([, init]) => init?.method === 'POST' && !(init.body as string).includes('run'),
    );
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({
      account_id: account.id,
      transaction_type: 'income',
      amount: '1200.00',
      description: 'Salary',
      frequency: 'monthly',
      interval: 1,
      category_id: 'cat-salary',
    });
  });

  it('validates amount and description', async () => {
    renderWithProviders(<RecurringPage />);
    await screen.findByText('Rent');
    await userEvent.click(screen.getByRole('button', { name: /new recurring rule/i }));
    const dialog = await screen.findByRole('dialog', { name: /new recurring rule/i });
    await userEvent.click(within(dialog).getByRole('button', { name: /create rule/i }));

    expect(await within(dialog).findByText(/greater than zero/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/short description/i)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
  });

  it('edits amount and description', async () => {
    renderWithProviders(<RecurringPage />);
    await screen.findByText('Rent');
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }));
    const dialog = await screen.findByRole('dialog', { name: /edit recurring rule/i });
    await userEvent.clear(within(dialog).getByLabelText(/amount/i));
    await userEvent.type(within(dialog).getByLabelText(/amount/i), '1100.00');
    await userEvent.clear(within(dialog).getByLabelText('Description'));
    await userEvent.type(within(dialog).getByLabelText('Description'), 'Rent (new)');
    await userEvent.click(within(dialog).getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH');
      expect(JSON.parse(String(patch?.[1]?.body))).toMatchObject({
        amount: '1100.00',
        description: 'Rent (new)',
      });
    });
  });

  it('runs a rule now and reports the result', async () => {
    renderWithProviders(<RecurringPage />);
    await screen.findByText('Rent');
    await userEvent.click(screen.getByRole('button', { name: /run now/i }));

    expect(await screen.findByText(/2 generated, 0 skipped/i)).toBeInTheDocument();
    expect(screen.getByText(/next 31 Mar 2026/i)).toBeInTheDocument();
  });

  it('pauses a rule', async () => {
    renderWithProviders(<RecurringPage />);
    await screen.findByText('Rent');
    await userEvent.click(screen.getByRole('button', { name: 'Pause' }));

    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH');
      expect(JSON.parse(String(patch?.[1]?.body))).toMatchObject({ is_active: false });
    });
  });

  it('deletes a rule after confirmation', async () => {
    renderWithProviders(<RecurringPage />);
    await screen.findByText('Rent');
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('dialog', { name: /delete recurring rule/i });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(true),
    );
  });

  it('shows an empty state', async () => {
    installApi([
      ...routes,
      { method: 'GET', path: '/api/v1/recurring-rules', response: jsonResponse(page([])) },
    ]);
    renderWithProviders(<RecurringPage />);

    expect(await screen.findByText(/no recurring rules/i)).toBeInTheDocument();
  });

  it('surfaces a load error', async () => {
    installApi([
      ...routes,
      {
        method: 'GET',
        path: '/api/v1/recurring-rules',
        response: jsonResponse({ detail: 'Boom' }, 500),
      },
    ]);
    renderWithProviders(<RecurringPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Boom');
  });
});

describe('RecurringPage branches', () => {
  it('creates a daily income rule', async () => {
    renderWithProviders(<RecurringPage />);
    await screen.findByText('Rent');
    await userEvent.click(screen.getByRole('button', { name: /new recurring rule/i }));
    const dialog = await screen.findByRole('dialog', { name: /new recurring rule/i });
    await userEvent.selectOptions(within(dialog).getByLabelText('Type'), 'income');
    await userEvent.selectOptions(within(dialog).getByLabelText('Frequency'), 'daily');
    expect(within(dialog).queryByLabelText(/day of month/i)).not.toBeInTheDocument();
    await userEvent.clear(within(dialog).getByLabelText(/every n periods/i));
    await userEvent.type(within(dialog).getByLabelText(/every n periods/i), '2');
    await userEvent.type(within(dialog).getByLabelText(/amount/i), '10.00');
    await userEvent.type(within(dialog).getByLabelText('Description'), 'Daily coffee');
    await userEvent.selectOptions(within(dialog).getByLabelText('Category'), 'cat-salary');
    await userEvent.click(within(dialog).getByRole('button', { name: /create rule/i }));

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        ([, init]) => init?.method === 'POST' && !(init.body as string).includes('run'),
      );
      expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({
        transaction_type: 'income',
        frequency: 'daily',
        interval: 2,
      });
    });
  });

  it('resumes an inactive rule and clears its end date', async () => {
    const inactive = { ...rule, is_active: false, ends_on: '2026-06-01' };
    const localFetch = installApi([
      ...routes,
      { method: 'GET', path: '/api/v1/recurring-rules', response: jsonResponse(page([inactive])) },
    ]);
    renderWithProviders(<RecurringPage />);
    await screen.findByText('Rent');
    expect(screen.getByText('Paused')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Resume' }));
    await waitFor(() => {
      const patch = localFetch.mock.calls.find(([, init]) => init?.method === 'PATCH');
      expect(JSON.parse(String(patch?.[1]?.body))).toMatchObject({ is_active: true });
    });

    await userEvent.click(screen.getByRole('button', { name: 'Edit' }));
    const dialog = await screen.findByRole('dialog', { name: /edit recurring rule/i });
    await userEvent.clear(within(dialog).getByLabelText(/ends on/i));
    await userEvent.click(within(dialog).getByRole('button', { name: /save changes/i }));
    await waitFor(() => {
      const patches = localFetch.mock.calls.filter(([, init]) => init?.method === 'PATCH');
      const last = patches[patches.length - 1];
      expect(JSON.parse(String(last?.[1]?.body))).toMatchObject({ ends_on: null });
    });
  });

  it('shows a run error', async () => {
    installApi([
      ...routes,
      {
        method: 'POST',
        path: `/api/v1/recurring-rules/${rule.id}/run`,
        response: jsonResponse({ detail: 'Rule is paused' }, 422),
      },
    ]);
    renderWithProviders(<RecurringPage />);
    await screen.findByText('Rent');
    await userEvent.click(screen.getByRole('button', { name: /run now/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Rule is paused');
  });

  it('cancels a delete', async () => {
    renderWithProviders(<RecurringPage />);
    await screen.findByText('Rent');
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('dialog', { name: /delete recurring rule/i });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
