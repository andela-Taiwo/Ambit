import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { App } from '@/app/App';

const renderWithProviders = (ui: ReactElement): void => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
};

const stubFetch = (body: unknown, status = 200): void => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  );
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('App shell', () => {
  it('renders the application name', () => {
    stubFetch({ status: 'ok' });
    renderWithProviders(<App />);

    expect(screen.getByRole('heading', { name: /finance tracker/i })).toBeInTheDocument();
  });

  it('exposes a main landmark for assistive technology', () => {
    stubFetch({ status: 'ok' });
    renderWithProviders(<App />);

    expect(screen.getByRole('main')).toBeInTheDocument();
  });

  it('shows a loading state while the backend status is in flight', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})));
    renderWithProviders(<App />);

    expect(screen.getByRole('status')).toHaveTextContent(/checking/i);
  });

  it('reports the backend as connected when health returns ok', async () => {
    stubFetch({ status: 'ok' });
    renderWithProviders(<App />);

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/connected/i);
    });
  });

  it('reports the backend as unavailable when health fails', async () => {
    stubFetch({ detail: 'boom' }, 503);
    renderWithProviders(<App />);

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/unavailable/i);
    });
  });
});
