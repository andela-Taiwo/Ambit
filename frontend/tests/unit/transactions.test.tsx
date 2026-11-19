import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { TransactionsPage } from '@/pages/TransactionsPage';
import {
  account,
  categories,
  installApi,
  investmentAccount,
  jsonResponse,
  noContentResponse,
  page,
  transaction,
} from './helpers/api';
import { renderWithProviders } from './helpers/render';

const transferLeg = {
  ...transaction,
  id: 'tx-2',
  transaction_type: 'transfer' as const,
  category_id: null,
  transfer_group_id: 'group-1',
  description: 'To savings',
  amount_minor: 5_000,
  signed_amount_minor: -5_000,
};

const transferResponse = {
  transfer_group_id: 'group-2',
  legs: [transferLeg, transferLeg],
};

const routes = [
  {
    method: 'GET',
    path: '/api/v1/transactions',
    response: jsonResponse(page([transaction, transferLeg], { total: 2 })),
  },
  {
    method: 'GET',
    path: '/api/v1/accounts',
    response: jsonResponse(page([account, investmentAccount])),
  },
  { method: 'GET', path: '/api/v1/categories', response: jsonResponse(page(categories)) },
  {
    method: 'POST',
    path: '/api/v1/transactions',
    response: jsonResponse({ ...transaction, id: 'tx-new' }, 201),
  },
  {
    method: 'PATCH',
    path: `/api/v1/transactions/${transaction.id}`,
    response: jsonResponse({ ...transaction, description: 'Updated shop' }),
  },
  {
    method: 'DELETE',
    path: `/api/v1/transactions/${transaction.id}`,
    response: noContentResponse(),
  },
  {
    method: 'POST',
    path: '/api/v1/transactions/transfers',
    response: jsonResponse(transferResponse, 201),
  },
  {
    method: 'POST',
    path: '/api/v1/transactions/import',
    response: jsonResponse({
      imported_count: 1,
      skipped_count: 0,
      error_count: 0,
      errors: [],
      batch_id: 'batch-1',
      dry_run: false,
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

describe('TransactionsPage', () => {
  it('lists transactions with account and category names', async () => {
    renderWithProviders(<TransactionsPage />);

    expect(await screen.findByText('Weekly shop')).toBeInTheDocument();
    expect(screen.getByText('To savings')).toBeInTheDocument();
    expect(screen.getAllByText('Current Account').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Groceries').length).toBeGreaterThan(0);
    expect(screen.getByText(/24\.99/)).toBeInTheDocument();
  });

  it('filters by account and resets the offset', async () => {
    renderWithProviders(<TransactionsPage />);
    await screen.findByText('Weekly shop');

    await userEvent.selectOptions(screen.getByLabelText('Account'), account.id);

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map(([input]) =>
        typeof input === 'string' ? input : input.toString(),
      );
      expect(
        urls.some((url) => url.includes(`account_id=${account.id}`) && url.includes('offset=0')),
      ).toBe(true);
    });
  });

  it('creates an expense and validates the amount', async () => {
    renderWithProviders(<TransactionsPage />);
    await screen.findByText('Weekly shop');
    await userEvent.click(screen.getByRole('button', { name: /new transaction/i }));

    const dialog = await screen.findByRole('dialog', { name: /new transaction/i });
    await userEvent.click(within(dialog).getByRole('button', { name: /add transaction/i }));
    expect(await within(dialog).findByText(/greater than zero/i)).toBeInTheDocument();

    await userEvent.type(within(dialog).getByLabelText(/amount/i), '14.50');
    await userEvent.selectOptions(within(dialog).getByLabelText('Category'), 'cat-groceries');
    await userEvent.type(within(dialog).getByLabelText('Description'), 'Lunch');
    await userEvent.click(within(dialog).getByRole('button', { name: /add transaction/i }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    const post = fetchMock.mock.calls.find(
      ([, init]) => init?.method === 'POST' && (init.body as string).includes('account_id'),
    );
    const body = JSON.parse(String(post?.[1]?.body)) as Record<string, unknown>;
    expect(body).toMatchObject({
      account_id: account.id,
      transaction_type: 'expense',
      amount: '14.50',
      currency: 'GBP',
      category_id: 'cat-groceries',
      description: 'Lunch',
    });
  });

  it('edits a non-transfer transaction', async () => {
    renderWithProviders(<TransactionsPage />);
    await screen.findByText('Weekly shop');
    const row = screen.getByText('Weekly shop').closest('tr');
    await userEvent.click(within(row as HTMLElement).getByRole('button', { name: 'Edit' }));

    const dialog = await screen.findByRole('dialog', { name: /edit transaction/i });
    await userEvent.clear(within(dialog).getByLabelText('Description'));
    await userEvent.type(within(dialog).getByLabelText('Description'), 'Updated shop');
    await userEvent.click(within(dialog).getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH');
      expect(JSON.parse(String(patch?.[1]?.body))).toMatchObject({ description: 'Updated shop' });
    });
  });

  it('disables editing for transfer legs', async () => {
    renderWithProviders(<TransactionsPage />);
    await screen.findByText('To savings');
    const row = screen.getByText('To savings').closest('tr');
    expect(within(row as HTMLElement).getByRole('button', { name: 'Edit' })).toBeDisabled();
  });

  it('creates a transfer between same-currency accounts', async () => {
    renderWithProviders(<TransactionsPage />);
    await screen.findByText('Weekly shop');
    await userEvent.click(screen.getByRole('button', { name: /^transfer$/i }));

    const dialog = await screen.findByRole('dialog', { name: /transfer between accounts/i });
    await userEvent.selectOptions(
      within(dialog).getByLabelText('To account'),
      investmentAccount.id,
    );
    await userEvent.type(within(dialog).getByLabelText(/amount/i), '50.00');
    await userEvent.click(within(dialog).getByRole('button', { name: /create transfer/i }));

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(([input, init]) => {
        const url = typeof input === 'string' ? input : input.toString();
        return init?.method === 'POST' && url.endsWith('/transactions/transfers');
      });
      expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({
        from_account_id: account.id,
        to_account_id: investmentAccount.id,
        amount: '50.00',
        currency: 'GBP',
      });
    });
  });

  it('imports a CSV and reports the counts', async () => {
    renderWithProviders(<TransactionsPage />);
    await screen.findByText('Weekly shop');
    await userEvent.click(screen.getByRole('button', { name: /import csv/i }));

    const dialog = await screen.findByRole('dialog', { name: /import transactions/i });
    await userEvent.click(within(dialog).getByRole('button', { name: /import csv/i }));

    expect(await within(dialog).findByText(/import complete/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/1 to import, 0 duplicates skipped/i)).toBeInTheDocument();
    const post = fetchMock.mock.calls.find(([input]) => {
      const url = typeof input === 'string' ? input : input.toString();
      return url.endsWith('/transactions/import');
    });
    const body = JSON.parse(String(post?.[1]?.body)) as Record<string, unknown>;
    expect(body).toMatchObject({ account_id: account.id, date_format: '%Y-%m-%d', dry_run: false });
  });

  it('shows row errors from an import failure', async () => {
    installApi([
      ...routes,
      {
        method: 'POST',
        path: '/api/v1/transactions/import',
        response: jsonResponse(
          {
            detail: '1 row failed validation',
            error_count: 1,
            errors: [{ row: 3, message: 'Date is empty' }],
          },
          422,
        ),
      },
    ]);
    renderWithProviders(<TransactionsPage />);
    await screen.findByText('Weekly shop');
    await userEvent.click(screen.getByRole('button', { name: /import csv/i }));
    const dialog = await screen.findByRole('dialog', { name: /import transactions/i });
    await userEvent.click(within(dialog).getByRole('button', { name: /import csv/i }));

    expect(await within(dialog).findByText(/row 3: date is empty/i)).toBeInTheDocument();
  });

  it('deletes after confirmation', async () => {
    renderWithProviders(<TransactionsPage />);
    await screen.findByText('Weekly shop');
    const row = screen.getByText('Weekly shop').closest('tr');
    await userEvent.click(within(row as HTMLElement).getByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('dialog', { name: /delete transaction/i });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(true),
    );
  });

  it('shows an empty state when filters match nothing', async () => {
    installApi([
      ...routes,
      { method: 'GET', path: '/api/v1/transactions', response: jsonResponse(page([])) },
    ]);
    renderWithProviders(<TransactionsPage />);

    expect(await screen.findByText(/no transactions match/i)).toBeInTheDocument();
  });
});

describe('TransactionsPage branches', () => {
  it('clears filters and changes each filter control', async () => {
    renderWithProviders(<TransactionsPage />);
    await screen.findByText('Weekly shop');

    await userEvent.selectOptions(screen.getByLabelText('Account'), account.id);
    await userEvent.selectOptions(screen.getByLabelText('Category'), 'cat-groceries');
    await userEvent.selectOptions(screen.getByLabelText('Type'), 'expense');
    const dateInputs = screen.getAllByDisplayValue('');
    await userEvent.type(dateInputs[0]!, '2026-01-01');
    await userEvent.click(screen.getByRole('button', { name: /clear filters/i }));

    expect(screen.getByLabelText('Account')).toHaveValue('');
    expect(screen.getByLabelText('Category')).toHaveValue('');
    expect(screen.getByLabelText('Type')).toHaveValue('');
  });

  it('creates an income transaction', async () => {
    renderWithProviders(<TransactionsPage />);
    await screen.findByText('Weekly shop');
    await userEvent.click(screen.getByRole('button', { name: /new transaction/i }));
    const dialog = await screen.findByRole('dialog', { name: /new transaction/i });
    await userEvent.selectOptions(within(dialog).getByLabelText('Type'), 'income');
    await userEvent.type(within(dialog).getByLabelText(/amount/i), '500.00');
    await userEvent.selectOptions(within(dialog).getByLabelText('Category'), 'cat-salary');
    await userEvent.click(within(dialog).getByRole('button', { name: /add transaction/i }));

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        ([, init]) => init?.method === 'POST' && (init.body as string).includes('transaction_type'),
      );
      expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({
        transaction_type: 'income',
        category_id: 'cat-salary',
      });
    });
  });

  it('validates a transfer with no same-currency destination', async () => {
    const ngn = { ...account, id: 'account-ngn', name: 'Naira', currency: 'NGN' };
    installApi([
      ...routes,
      { method: 'GET', path: '/api/v1/accounts', response: jsonResponse(page([account, ngn])) },
    ]);
    renderWithProviders(<TransactionsPage />);
    await screen.findByText('Weekly shop');
    await userEvent.click(screen.getByRole('button', { name: /^transfer$/i }));
    const dialog = await screen.findByRole('dialog', { name: /transfer between accounts/i });
    await userEvent.type(within(dialog).getByLabelText(/amount/i), '50.00');
    await userEvent.click(within(dialog).getByRole('button', { name: /create transfer/i }));

    expect(await within(dialog).findByText(/choose a destination account/i)).toBeInTheDocument();
  });

  it('supports a dry-run import with custom mapping fields', async () => {
    const localFetch = installApi([
      ...routes,
      {
        method: 'POST',
        path: '/api/v1/transactions/import',
        response: jsonResponse({
          imported_count: 1,
          skipped_count: 0,
          error_count: 0,
          errors: [],
          batch_id: null,
          dry_run: true,
        }),
      },
    ]);
    renderWithProviders(<TransactionsPage />);
    await screen.findByText('Weekly shop');
    await userEvent.click(screen.getByRole('button', { name: /import csv/i }));
    const dialog = await screen.findByRole('dialog', { name: /import transactions/i });
    await userEvent.type(within(dialog).getByLabelText(/category column/i), 'category');
    await userEvent.type(within(dialog).getByLabelText(/type column/i), 'type');
    await userEvent.type(within(dialog).getByLabelText(/bank reference column/i), 'ref');
    await userEvent.click(within(dialog).getByLabelText(/validate and report/i));
    await userEvent.click(within(dialog).getByRole('button', { name: /validate only/i }));

    expect(await within(dialog).findByText(/validation complete/i)).toBeInTheDocument();
    const post = localFetch.mock.calls.find(([input]) =>
      (typeof input === 'string' ? input : input.toString()).endsWith('/transactions/import'),
    );
    const body = JSON.parse(String(post?.[1]?.body)) as Record<string, unknown>;
    expect(body).toMatchObject({ dry_run: true });
    expect(body.mapping).toMatchObject({ category: 'category', type: 'type', external_id: 'ref' });
  });

  it('paginates to the next page', async () => {
    const localFetch = installApi([
      ...routes,
      {
        method: 'GET',
        path: '/api/v1/transactions',
        response: jsonResponse(page([transaction], { total: 120 })),
      },
    ]);
    renderWithProviders(<TransactionsPage />);
    await screen.findByText('Weekly shop');
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => {
      const urls = localFetch.mock.calls.map(([input]) =>
        typeof input === 'string' ? input : input.toString(),
      );
      expect(urls.some((url) => url.includes('offset=50'))).toBe(true);
    });
  });

  it('cancels a delete', async () => {
    renderWithProviders(<TransactionsPage />);
    await screen.findByText('Weekly shop');
    const row = screen.getByText('Weekly shop').closest('tr');
    await userEvent.click(within(row as HTMLElement).getByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('dialog', { name: /delete transaction/i });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
