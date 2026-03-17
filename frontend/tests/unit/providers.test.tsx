import { useQueryClient } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import type { JSX } from 'react';
import { describe, expect, it } from 'vitest';

import { AppProviders } from '@/app/providers';
import { createQueryClient } from '@/app/queryClient';

const QueryClientProbe = (): JSX.Element => {
  const client = useQueryClient();
  return <span data-testid="probe">{String(client.getDefaultOptions().queries?.retry)}</span>;
};

describe('AppProviders', () => {
  it('renders its children', () => {
    render(
      <AppProviders>
        <p>child content</p>
      </AppProviders>,
    );

    expect(screen.getByText('child content')).toBeInTheDocument();
  });

  it('supplies a query client to the tree', () => {
    render(
      <AppProviders>
        <QueryClientProbe />
      </AppProviders>,
    );

    expect(screen.getByTestId('probe')).toHaveTextContent('1');
  });
});

describe('createQueryClient', () => {
  it('does not refetch on window focus', () => {
    const options = createQueryClient().getDefaultOptions();

    expect(options.queries?.refetchOnWindowFocus).toBe(false);
  });

  it('sets a non-zero stale time so the UI is not chatty', () => {
    const options = createQueryClient().getDefaultOptions();

    expect(options.queries?.staleTime).toBeGreaterThan(0);
  });
});
