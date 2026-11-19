import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { CategoriesPage } from '@/pages/CategoriesPage';
import { categories, installApi, jsonResponse, noContentResponse, page } from './helpers/api';
import { renderWithProviders } from './helpers/render';

const utilities = {
  ...categories[1]!,
  id: 'cat-utilities',
  name: 'Utilities',
  parent_id: 'cat-housing',
};

const routes = [
  {
    method: 'GET',
    path: '/api/v1/categories',
    response: jsonResponse(page([...categories, utilities])),
  },
  {
    method: 'POST',
    path: '/api/v1/categories',
    response: jsonResponse({ ...categories[0]!, id: 'cat-new', name: 'Travel' }, 201),
  },
  {
    method: 'PATCH',
    path: '/api/v1/categories/cat-groceries',
    response: jsonResponse({ ...categories[0]!, name: 'Food' }),
  },
  { method: 'DELETE', path: '/api/v1/categories/cat-groceries', response: noContentResponse() },
] as const;

let fetchMock: ReturnType<typeof vi.fn<typeof fetch>>;

beforeEach(() => {
  fetchMock = installApi(routes);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('CategoriesPage', () => {
  it('renders the hierarchy and kinds', async () => {
    renderWithProviders(<CategoriesPage />);

    expect(await screen.findByText('Housing')).toBeInTheDocument();
    expect(screen.getByText('Utilities')).toBeInTheDocument();
    expect(screen.getByText('Salary')).toBeInTheDocument();
    expect(screen.getByText('Income')).toBeInTheDocument();
  });

  it('creates a child category', async () => {
    renderWithProviders(<CategoriesPage />);
    await screen.findByText('Housing');
    await userEvent.click(screen.getByRole('button', { name: /new category/i }));

    const dialog = await screen.findByRole('dialog', { name: /new category/i });
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Travel');
    await userEvent.selectOptions(within(dialog).getByLabelText('Parent category'), 'cat-housing');
    await userEvent.click(within(dialog).getByRole('button', { name: /create category/i }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
    expect(post?.[1]?.body).toBe(
      JSON.stringify({ name: 'Travel', kind: 'expense', parent_id: 'cat-housing' }),
    );
  });

  it('validates the name before posting', async () => {
    renderWithProviders(<CategoriesPage />);
    await screen.findByText('Housing');
    await userEvent.click(screen.getByRole('button', { name: /new category/i }));
    const dialog = await screen.findByRole('dialog', { name: /new category/i });
    await userEvent.click(within(dialog).getByRole('button', { name: /create category/i }));

    expect(await screen.findByText(/enter a category name/i)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
  });

  it('renames a category', async () => {
    renderWithProviders(<CategoriesPage />);
    await screen.findByText('Groceries');
    const row = screen.getByText('Groceries').closest('tr');
    expect(row).not.toBeNull();
    await userEvent.click(within(row as HTMLElement).getByRole('button', { name: 'Edit' }));

    const dialog = await screen.findByRole('dialog', { name: /edit category/i });
    await userEvent.clear(within(dialog).getByLabelText('Name'));
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Food');
    await userEvent.click(within(dialog).getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH');
      expect(patch?.[1]?.body).toBe(JSON.stringify({ name: 'Food', parent_id: null }));
    });
  });

  it('archives a category', async () => {
    renderWithProviders(<CategoriesPage />);
    await screen.findByText('Groceries');
    const row = screen.getByText('Groceries').closest('tr');
    await userEvent.click(within(row as HTMLElement).getByRole('button', { name: 'Archive' }));

    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH');
      expect(patch?.[1]?.body).toBe(JSON.stringify({ is_archived: true }));
    });
  });

  it('deletes after confirmation', async () => {
    renderWithProviders(<CategoriesPage />);
    await screen.findByText('Groceries');
    const row = screen.getByText('Groceries').closest('tr');
    await userEvent.click(within(row as HTMLElement).getByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('dialog', { name: /delete category/i });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(true);
    });
  });

  it('toggles archived categories in the query', async () => {
    renderWithProviders(<CategoriesPage />);
    await screen.findByText('Groceries');
    await userEvent.click(screen.getByLabelText(/show archived categories/i));

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
        path: '/api/v1/categories',
        response: jsonResponse({ detail: 'No categories' }, 500),
      },
    ]);
    renderWithProviders(<CategoriesPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent('No categories');
  });
});

describe('CategoriesPage branches', () => {
  it('creates an income category and resets the parent on kind change', async () => {
    renderWithProviders(<CategoriesPage />);
    await screen.findByText('Housing');
    await userEvent.click(screen.getByRole('button', { name: /new category/i }));
    const dialog = await screen.findByRole('dialog', { name: /new category/i });
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Bonus');
    await userEvent.selectOptions(within(dialog).getByLabelText('Parent category'), 'cat-housing');
    await userEvent.selectOptions(within(dialog).getByLabelText('Kind'), 'income');
    expect(within(dialog).getByLabelText('Parent category')).toHaveValue('');
    await userEvent.click(within(dialog).getByRole('button', { name: /create category/i }));

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
      expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({
        name: 'Bonus',
        kind: 'income',
        parent_id: null,
      });
    });
  });

  it('restores an archived category', async () => {
    const archived = { ...categories[0]!, is_archived: true };
    const localFetch = installApi([
      { method: 'GET', path: '/api/v1/categories', response: jsonResponse(page([archived])) },
      {
        method: 'PATCH',
        path: '/api/v1/categories/cat-groceries',
        response: jsonResponse(categories[0]!),
      },
    ]);
    renderWithProviders(<CategoriesPage />);
    expect(await screen.findByText('Archived')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Restore' }));
    await waitFor(() => {
      const patch = localFetch.mock.calls.find(([, init]) => init?.method === 'PATCH');
      expect(patch?.[1]?.body).toBe(JSON.stringify({ is_archived: false }));
    });
  });

  it('clears a parent when editing a child', async () => {
    renderWithProviders(<CategoriesPage />);
    await screen.findByText('Utilities');
    const row = screen.getByText('Utilities').closest('tr');
    await userEvent.click(within(row as HTMLElement).getByRole('button', { name: 'Edit' }));
    const dialog = await screen.findByRole('dialog', { name: /edit category/i });
    await userEvent.selectOptions(within(dialog).getByLabelText('Parent category'), '');
    await userEvent.click(within(dialog).getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH');
      expect(JSON.parse(String(patch?.[1]?.body))).toMatchObject({ parent_id: null });
    });
  });

  it('shows a save error from the API', async () => {
    const localFetch = installApi([
      ...routes,
      {
        method: 'POST',
        path: '/api/v1/categories',
        response: jsonResponse({ detail: 'Duplicate category' }, 409),
      },
    ]);
    renderWithProviders(<CategoriesPage />);
    await screen.findByText('Housing');
    await userEvent.click(screen.getByRole('button', { name: /new category/i }));
    const dialog = await screen.findByRole('dialog', { name: /new category/i });
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Groceries');
    await userEvent.click(within(dialog).getByRole('button', { name: /create category/i }));

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Duplicate category');
    expect(localFetch).toHaveBeenCalled();
  });

  it('cancels a delete', async () => {
    renderWithProviders(<CategoriesPage />);
    await screen.findByText('Groceries');
    const row = screen.getByText('Groceries').closest('tr');
    await userEvent.click(within(row as HTMLElement).getByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('dialog', { name: /delete category/i });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
