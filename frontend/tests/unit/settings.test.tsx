import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useAuthStore } from '@/features/auth/store';
import { SettingsPage } from '@/pages/SettingsPage';
import { installApi, jsonResponse, page, user } from './helpers/api';
import { renderWithProviders } from './helpers/render';

const rate = {
  id: 'rate-1',
  base_currency: 'GBP',
  quote_currency: 'USD',
  rate: '1.27',
  as_of: '2026-01-01T00:00:00Z',
  source: 'manual',
  fetched_at: '2026-01-01T00:00:00Z',
};

const routes = [
  { method: 'GET', path: '/health', response: jsonResponse({ status: 'ok' }) },
  { method: 'GET', path: '/api/v1/exchange-rates', response: jsonResponse(page([rate])) },
  {
    method: 'POST',
    path: '/api/v1/exchange-rates',
    response: jsonResponse({ ...rate, id: 'rate-new' }, 201),
  },
  {
    method: 'GET',
    path: '/api/v1/export',
    response: new Response('{"schema_version":1}', {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Content-Disposition': 'attachment; filename="budgetting-export.json"',
      },
    }),
  },
] as const;

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>;

beforeEach(() => {
  useAuthStore.setState({ status: 'authenticated', user });
  fetchMock = installApi(routes);
  Object.defineProperty(URL, 'createObjectURL', {
    value: vi.fn(() => 'blob:export'),
    configurable: true,
  });
  Object.defineProperty(URL, 'revokeObjectURL', { value: vi.fn(), configurable: true });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('SettingsPage', () => {
  it('shows the profile and recorded rates', async () => {
    renderWithProviders(<SettingsPage />);

    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
    expect(screen.getByText('ada@example.com')).toBeInTheDocument();
    expect(await screen.findByText('GBP → USD')).toBeInTheDocument();
    expect(screen.getByText('1.27')).toBeInTheDocument();
    expect(screen.getByText('manual')).toBeInTheDocument();
    expect(await screen.findByRole('status')).toHaveTextContent('Backend connected');
  });

  it('records a manual rate', async () => {
    renderWithProviders(<SettingsPage />);
    await screen.findByText('GBP → USD');

    const form = screen
      .getByRole('heading', { name: /record a manual exchange rate/i })
      .closest('section');
    expect(form).not.toBeNull();
    await userEvent.type(within(form as HTMLElement).getByLabelText('Rate'), '1.5');
    await userEvent.click(within(form as HTMLElement).getByRole('button', { name: /save rate/i }));

    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
    const body = JSON.parse(String(post?.[1]?.body)) as Record<string, unknown>;
    expect(body).toMatchObject({ base_currency: 'GBP', quote_currency: 'USD' });
    expect(typeof body.rate).toBe('string');
  });

  it('validates the rate and currency pair', async () => {
    renderWithProviders(<SettingsPage />);
    await screen.findByText('GBP → USD');
    const form = screen
      .getByRole('heading', { name: /record a manual exchange rate/i })
      .closest('section');
    await userEvent.click(within(form as HTMLElement).getByRole('button', { name: /save rate/i }));
    expect(await within(form as HTMLElement).findByText(/positive rate/i)).toBeInTheDocument();

    await userEvent.type(within(form as HTMLElement).getByLabelText('Rate'), '1.27');
    await userEvent.selectOptions(
      within(form as HTMLElement).getByLabelText('Quote currency'),
      'GBP',
    );
    await userEvent.click(within(form as HTMLElement).getByRole('button', { name: /save rate/i }));
    expect(
      await within(form as HTMLElement).findByText(/different currencies/i),
    ).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
  });

  it('downloads the full JSON export', async () => {
    renderWithProviders(<SettingsPage />);
    await screen.findByText('GBP → USD');

    await userEvent.click(screen.getByRole('button', { name: /export all data/i }));

    expect(await screen.findByText(/downloaded budgetting-export\.json/i)).toBeInTheDocument();
    expect(URL.createObjectURL).toHaveBeenCalled();
  });
});

describe('SettingsPage branches', () => {
  it('changes currencies and reports a save failure', async () => {
    installApi([
      ...routes,
      {
        method: 'POST',
        path: '/api/v1/exchange-rates',
        response: jsonResponse({ detail: 'Rate already exists' }, 409),
      },
    ]);
    renderWithProviders(<SettingsPage />);
    await screen.findByText('GBP → USD');
    const form = screen
      .getByRole('heading', { name: /record a manual exchange rate/i })
      .closest('section');
    await userEvent.selectOptions(
      within(form as HTMLElement).getByLabelText('Base currency'),
      'USD',
    );
    await userEvent.selectOptions(
      within(form as HTMLElement).getByLabelText('Quote currency'),
      'EUR',
    );
    await userEvent.type(within(form as HTMLElement).getByLabelText('Rate'), '0.9');
    await userEvent.click(within(form as HTMLElement).getByRole('button', { name: /save rate/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Rate already exists');
  });

  it('surfaces an export failure', async () => {
    installApi([
      ...routes,
      {
        method: 'GET',
        path: '/api/v1/export',
        response: jsonResponse({ detail: 'Export failed' }, 500),
      },
    ]);
    renderWithProviders(<SettingsPage />);
    await screen.findByText('GBP → USD');
    await userEvent.click(screen.getByRole('button', { name: /export all data/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Export failed');
  });

  it('shows an empty rate list', async () => {
    installApi([
      ...routes,
      { method: 'GET', path: '/api/v1/exchange-rates', response: jsonResponse(page([])) },
    ]);
    renderWithProviders(<SettingsPage />);

    expect(await screen.findByText(/no rates recorded/i)).toBeInTheDocument();
  });
});

describe('SettingsPage backend status', () => {
  it('reports an unavailable backend', async () => {
    installApi([
      ...routes,
      { method: 'GET', path: '/health', response: jsonResponse({ detail: 'down' }, 503) },
    ]);
    renderWithProviders(<SettingsPage />);

    expect(await screen.findByRole('status')).toHaveTextContent('Backend unavailable');
  });
});
