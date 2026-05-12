import { useMemo, useState, type SyntheticEvent, type JSX } from 'react';

import {
  useCategories,
  useCreateCategory,
  useDeleteCategory,
  useUpdateCategory,
} from '@/api/hooks';
import type { CategoryKind, CategoryResponse } from '@/api/types';
import {
  Alert,
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorAlert,
  LoadingState,
  Modal,
  PageHeader,
  SelectInput,
  TextInput,
} from '@/components/ui';
import { categoryKindLabels } from '@/lib/labels';

const CategoryForm = ({
  category,
  categories,
  onClose,
}: {
  category: CategoryResponse | null;
  categories: CategoryResponse[];
  onClose: () => void;
}): JSX.Element => {
  const create = useCreateCategory();
  const update = useUpdateCategory();
  const [name, setName] = useState(category?.name ?? '');
  const [kind, setKind] = useState<CategoryKind>(category?.kind ?? 'expense');
  const [parentId, setParentId] = useState(category?.parent_id ?? '');
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);

  const descendants = useMemo(() => {
    if (category === null) return new Set<string>();
    const children = new Map<string, string[]>();
    for (const item of categories) {
      if (item.parent_id !== null) {
        children.set(item.parent_id, [...(children.get(item.parent_id) ?? []), item.id]);
      }
    }
    const result = new Set<string>([category.id]);
    const stack = [category.id];
    while (stack.length > 0) {
      const current = stack.pop();
      if (current === undefined) continue;
      for (const child of children.get(current) ?? []) {
        result.add(child);
        stack.push(child);
      }
    }
    return result;
  }, [categories, category]);

  const parentOptions = categories.filter(
    (item) => item.kind === kind && !item.is_archived && !descendants.has(item.id),
  );

  const onSubmit = async (event: SyntheticEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setError(null);
    if (name.trim() === '') {
      setFieldError('Enter a category name');
      return;
    }
    setFieldError(null);

    try {
      if (category === null) {
        await create.mutateAsync({
          name: name.trim(),
          kind,
          parent_id: parentId === '' ? null : parentId,
        });
      } else {
        await update.mutateAsync({
          id: category.id,
          body: { name: name.trim(), parent_id: parentId === '' ? null : parentId },
        });
      }
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save the category');
    }
  };

  return (
    <Modal
      open
      title={category === null ? 'New category' : 'Edit category'}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            form="category-form"
            isLoading={create.isPending || update.isPending}
          >
            {category === null ? 'Create category' : 'Save changes'}
          </Button>
        </>
      }
    >
      <form
        id="category-form"
        className="space-y-4"
        onSubmit={(event) => void onSubmit(event)}
        noValidate
      >
        {error !== null ? <Alert variant="error">{error}</Alert> : null}
        <TextInput
          label="Name"
          required
          value={name}
          {...(fieldError !== null ? { error: fieldError } : {})}
          onChange={(event) => setName(event.target.value)}
        />
        {category === null ? (
          <SelectInput
            label="Kind"
            value={kind}
            onChange={(event) => {
              setKind(event.target.value as CategoryKind);
              setParentId('');
            }}
          >
            <option value="expense">Expense</option>
            <option value="income">Income</option>
          </SelectInput>
        ) : (
          <p className="text-xs text-slate-500">Kind cannot be changed after creation.</p>
        )}
        <SelectInput
          label="Parent category"
          value={parentId}
          onChange={(event) => setParentId(event.target.value)}
        >
          <option value="">None (top level)</option>
          {parentOptions.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </SelectInput>
      </form>
    </Modal>
  );
};

export const CategoriesPage = (): JSX.Element => {
  const [includeArchived, setIncludeArchived] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<CategoryResponse | null>(null);
  const [deleting, setDeleting] = useState<CategoryResponse | null>(null);
  const categories = useCategories(includeArchived);
  const update = useUpdateCategory();
  const remove = useDeleteCategory();
  const [error, setError] = useState<string | null>(null);

  const all = categories.data?.items ?? [];
  const byParent = new Map<string | null, CategoryResponse[]>();
  for (const category of all) {
    byParent.set(category.parent_id, [...(byParent.get(category.parent_id) ?? []), category]);
  }
  const ordered: Array<{ category: CategoryResponse; depth: number }> = [];
  const walk = (parentId: string | null, depth: number): void => {
    for (const category of (byParent.get(parentId) ?? []).sort((a, b) =>
      a.name.localeCompare(b.name),
    )) {
      ordered.push({ category, depth });
      walk(category.id, depth + 1);
    }
  };
  walk(null, 0);

  const toggleArchive = async (category: CategoryResponse): Promise<void> => {
    setError(null);
    try {
      await update.mutateAsync({
        id: category.id,
        body: { is_archived: !category.is_archived },
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not update the category');
    }
  };

  const confirmDelete = async (): Promise<void> => {
    if (deleting === null) return;
    setError(null);
    try {
      await remove.mutateAsync(deleting.id);
      setDeleting(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not delete the category');
    }
  };

  return (
    <div>
      <PageHeader
        title="Categories"
        description="Classify income and expenses. Child categories roll up into their parent for budgets and reports."
        actions={<Button onClick={() => setFormOpen(true)}>New category</Button>}
      />

      {error !== null ? <ErrorAlert error={error} /> : null}
      <div className="mb-4 flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(event) => setIncludeArchived(event.target.checked)}
          />
          Show archived categories
        </label>
      </div>

      {categories.error !== null ? <ErrorAlert error={categories.error} /> : null}
      {categories.isPending ? <LoadingState label="Loading categories…" /> : null}

      {!categories.isPending && ordered.length === 0 ? (
        <EmptyState
          title="No categories yet"
          description="Create categories for the things you spend and earn."
          action={<Button onClick={() => setFormOpen(true)}>Create a category</Button>}
        />
      ) : null}

      {ordered.length > 0 ? (
        <Card className="overflow-x-auto p-0">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th scope="col" className="px-4 py-3 text-left font-medium text-slate-600">
                  Name
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium text-slate-600">
                  Kind
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium text-slate-600">
                  Status
                </th>
                <th scope="col" className="px-4 py-3 text-right font-medium text-slate-600">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {ordered.map(({ category, depth }) => (
                <tr key={category.id}>
                  <td
                    className="px-4 py-3 font-medium"
                    style={{ paddingLeft: `${String(16 + depth * 20)}px` }}
                  >
                    {depth > 0 ? (
                      <span aria-hidden="true" className="mr-2 text-slate-400">
                        ↳
                      </span>
                    ) : null}
                    {category.name}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={category.kind === 'income' ? 'success' : 'neutral'}>
                      {categoryKindLabels[category.kind]}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    {category.is_archived ? (
                      <Badge tone="neutral">Archived</Badge>
                    ) : (
                      <Badge tone="info">Active</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" size="sm" onClick={() => setEditing(category)}>
                        Edit
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => void toggleArchive(category)}
                      >
                        {category.is_archived ? 'Restore' : 'Archive'}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setDeleting(category)}>
                        Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ) : null}

      {formOpen || editing !== null ? (
        <CategoryForm
          category={editing}
          categories={all}
          onClose={() => {
            setFormOpen(false);
            setEditing(null);
          }}
        />
      ) : null}

      <ConfirmDialog
        open={deleting !== null}
        title="Delete category?"
        message="Transactions keep their history but become uncategorized. Child categories are removed."
        onConfirm={() => void confirmDelete()}
        onCancel={() => setDeleting(null)}
        isLoading={remove.isPending}
      />
    </div>
  );
};
