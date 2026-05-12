import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AccountsPage } from '@/pages/AccountsPage';
import { account, installApi, jsonResponse, noContentResponse, page } from './helpers/api';
import { renderWithProviders } from './helpers/render';

const balance = {
  account_id: account.id,
  currency: 'GBP',
  balance_minor: 130_000,
  balance: '1300.00',
};

const routes = [
  { method: 'GET', path: '/api/v1/accounts', response: jsonResponse(page([account])) },
  {
    method: 'GET',
    path: `/api/v1/accounts/${account.id}/balance`,
    response: jsonResponse(balance),
  },
  {
    method: 'POST',
    path: '/api/v1/accounts',
    response: jsonResponse({ ...account, id: 'account-new', name: 'Savings' }, 201),
  },
  {
    method: 'PATCH',
    path: `/api/v1/accounts/${account.id}`,
    response: jsonResponse({ ...account, name: 'Renamed' }),
  },
  { method: 'DELETE', path: `/api/v1/accounts/${account.id}`, response: noContentResponse() },
] as const;

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>;

beforeEach(() => {
  fetchMock = installApi(routes);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('AccountsPage', () => {
  it('lists accounts with their derived balances', async () => {
    renderWithProviders(<AccountsPage />);

    expect(await screen.findByText('Current Account')).toBeInTheDocument();
    expect(await screen.findByText('£1,300.00')).toBeInTheDocument();
    expect(screen.getByText('Current account')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('creates an account with a validated opening balance', async () => {
    renderWithProviders(<AccountsPage />);
    await userEvent.click(screen.getByRole('button', { name: /new account/i }));

    const dialog = await screen.findByRole('dialog', { name: /new account/i });
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Savings');
    await userEvent.selectOptions(within(dialog).getByLabelText('Type'), 'savings');
    await userEvent.clear(within(dialog).getByLabelText('Opening balance'));
    await userEvent.type(within(dialog).getByLabelText('Opening balance'), '2500.50');
    await userEvent.click(within(dialog).getByRole('button', { name: /create account/i }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
    expect(post?.[1]?.body).toBe(
      JSON.stringify({
        name: 'Savings',
        account_type: 'savings',
        currency: 'GBP',
        opening_balance: '2500.50',
      }),
    );
  });

  it('rejects an invalid opening balance before calling the API', async () => {
    renderWithProviders(<AccountsPage />);
    await userEvent.click(screen.getByRole('button', { name: /new account/i }));
    const dialog = await screen.findByRole('dialog', { name: /new account/i });
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Savings');
    await userEvent.clear(within(dialog).getByLabelText('Opening balance'));
    await userEvent.type(within(dialog).getByLabelText('Opening balance'), '10.005');
    await userEvent.click(within(dialog).getByRole('button', { name: /create account/i }));

    expect(await screen.findByText(/valid opening balance/i)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
  });

  it('renames an account', async () => {
    renderWithProviders(<AccountsPage />);
    await screen.findByText('Current Account');
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }));

    const dialog = await screen.findByRole('dialog', { name: /edit account/i });
    await userEvent.clear(within(dialog).getByLabelText('Name'));
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Renamed');
    await userEvent.click(within(dialog).getByRole('button', { name: /save changes/i }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH');
    expect(patch?.[1]?.body).toBe(JSON.stringify({ name: 'Renamed', account_type: 'current' }));
  });

  it('archives and restores an account', async () => {
    renderWithProviders(<AccountsPage />);
    await screen.findByText('Current Account');
    await userEvent.click(screen.getByRole('button', { name: 'Archive' }));

    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH');
      expect(patch?.[1]?.body).toBe(JSON.stringify({ is_archived: true }));
    });
  });

  it('deletes after confirmation', async () => {
    renderWithProviders(<AccountsPage />);
    await screen.findByText('Current Account');
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('dialog', { name: /delete account/i });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(true);
    });
  });

  it('toggles archived accounts in the query', async () => {
    renderWithProviders(<AccountsPage />);
    await screen.findByText('Current Account');
    await userEvent.click(screen.getByLabelText(/show archived accounts/i));

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map(([input]) =>
        typeof input === 'string' ? input : input.toString(),
      );
      expect(urls.some((url) => url.includes('include_archived=true'))).toBe(true);
    });
  });

  it('surfaces a load error', async () => {
    installApi([
      {
        method: 'GET',
        path: '/api/v1/accounts',
        response: jsonResponse({ detail: 'Server exploded' }, 500),
      },
    ]);
    renderWithProviders(<AccountsPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Server exploded');
  });
});

describe('AccountsPage branches', () => {
  it('shows archived accounts and restores them', async () => {
    const archived = { ...account, is_archived: true };
    const localFetch = installApi([
      { method: 'GET', path: '/api/v1/accounts', response: jsonResponse(page([archived])) },
      {
        method: 'GET',
        path: `/api/v1/accounts/${account.id}/balance`,
        response: jsonResponse(balance),
      },
      { method: 'PATCH', path: `/api/v1/accounts/${account.id}`, response: jsonResponse(account) },
    ]);
    renderWithProviders(<AccountsPage />);

    expect(await screen.findByText('Archived')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Restore' }));
    await waitFor(() => {
      const patch = localFetch.mock.calls.find(([, init]) => init?.method === 'PATCH');
      expect(patch?.[1]?.body).toBe(JSON.stringify({ is_archived: false }));
    });
  });

  it('validates an empty edit name', async () => {
    renderWithProviders(<AccountsPage />);
    await screen.findByText('Current Account');
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }));
    const dialog = await screen.findByRole('dialog', { name: /edit account/i });
    await userEvent.clear(within(dialog).getByLabelText('Name'));
    await userEvent.click(within(dialog).getByRole('button', { name: /save changes/i }));

    expect(await within(dialog).findByText(/enter an account name/i)).toBeInTheDocument();
  });

  it('shows a create error from the API', async () => {
    installApi([
      ...routes,
      {
        method: 'POST',
        path: '/api/v1/accounts',
        response: jsonResponse({ detail: 'Name already exists' }, 409),
      },
    ]);
    renderWithProviders(<AccountsPage />);
    await screen.findByText('Current Account');
    await userEvent.click(screen.getByRole('button', { name: /new account/i }));
    const dialog = await screen.findByRole('dialog', { name: /new account/i });
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Current Account');
    await userEvent.click(within(dialog).getByRole('button', { name: /create account/i }));

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Name already exists');
  });

  it('cancels a delete', async () => {
    renderWithProviders(<AccountsPage />);
    await screen.findByText('Current Account');
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('dialog', { name: /delete account/i });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
