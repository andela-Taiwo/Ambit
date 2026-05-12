import { useState, type SyntheticEvent, type JSX } from 'react';

import {
  useBudgetStatus,
  useBudgets,
  useCategories,
  useCreateBudget,
  useDeleteBudget,
  useUpdateBudget,
} from '@/api/hooks';
import type { BudgetResponse, CategoryResponse } from '@/api/types';
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
  ProgressBar,
  SelectInput,
  StatCard,
  TextInput,
} from '@/components/ui';
import { addMonthsToMonth, currentMonth, monthLabel, monthStartIso } from '@/lib/dates';
import { budgetStatusLabels, budgetStatusTone } from '@/lib/labels';
import {
  SUPPORTED_CURRENCIES,
  formatMoney,
  formatPercent,
  minorToInput,
  parseAmountToMinor,
} from '@/lib/money';

const BudgetForm = ({
  budget,
  categories,
  onClose,
}: {
  budget: BudgetResponse | null;
  categories: CategoryResponse[];
  onClose: () => void;
}): JSX.Element => {
  const create = useCreateBudget();
  const update = useUpdateBudget();
  const expenseCategories = categories.filter(
    (category) => category.kind === 'expense' && !category.is_archived,
  );
  const [categoryId, setCategoryId] = useState(
    budget?.category_id ?? expenseCategories[0]?.id ?? '',
  );
  const [amount, setAmount] = useState(
    budget === null ? '' : minorToInput(budget.amount_minor, budget.currency),
  );
  const [currency, setCurrency] = useState(budget?.currency ?? 'GBP');
  const [startsOn, setStartsOn] = useState(budget?.starts_on ?? monthStartIso(currentMonth()));
  const [endsOn, setEndsOn] = useState(budget?.ends_on ?? '');
  const [rollover, setRollover] = useState(budget?.rollover_enabled ?? false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const onSubmit = async (event: SyntheticEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setError(null);
    const nextErrors: Record<string, string> = {};
    const minor = parseAmountToMinor(amount, currency);
    if (categoryId === '') nextErrors.category = 'Choose a category';
    if (minor === null) nextErrors.amount = 'Enter a valid limit';
    setFieldErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0 || minor === null) return;

    try {
      if (budget === null) {
        await create.mutateAsync({
          category_id: categoryId,
          amount: minorToInput(minor, currency),
          currency,
          starts_on: startsOn,
          ...(endsOn !== '' ? { ends_on: endsOn } : {}),
          rollover_enabled: rollover,
        });
      } else {
        await update.mutateAsync({
          id: budget.id,
          body: {
            amount: minorToInput(minor, currency),
            ends_on: endsOn === '' ? null : endsOn,
            rollover_enabled: rollover,
          },
        });
      }
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save the budget');
    }
  };

  return (
    <Modal
      open
      title={budget === null ? 'New budget' : 'Edit budget'}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="budget-form" isLoading={create.isPending || update.isPending}>
            {budget === null ? 'Create budget' : 'Save changes'}
          </Button>
        </>
      }
    >
      <form
        id="budget-form"
        className="space-y-4"
        onSubmit={(event) => void onSubmit(event)}
        noValidate
      >
        {error !== null ? <Alert variant="error">{error}</Alert> : null}
        <SelectInput
          label="Category"
          value={categoryId}
          disabled={budget !== null}
          {...(fieldErrors.category !== undefined ? { error: fieldErrors.category } : {})}
          onChange={(event) => setCategoryId(event.target.value)}
        >
          <option value="">Choose an expense category</option>
          {expenseCategories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </SelectInput>
        <TextInput
          label={`Monthly limit (${currency})`}
          inputMode="decimal"
          required
          value={amount}
          {...(fieldErrors.amount !== undefined ? { error: fieldErrors.amount } : {})}
          onChange={(event) => setAmount(event.target.value)}
        />
        {budget === null ? (
          <>
            <SelectInput
              label="Currency"
              value={currency}
              onChange={(event) => setCurrency(event.target.value)}
            >
              {SUPPORTED_CURRENCIES.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </SelectInput>
            <TextInput
              label="Starts on"
              type="date"
              required
              value={startsOn}
              hint="Must be the first day of a month."
              onChange={(event) => setStartsOn(event.target.value)}
            />
          </>
        ) : null}
        <TextInput
          label="Ends on (optional)"
          type="date"
          value={endsOn}
          hint="Exclusive first day of the month the budget stops applying."
          onChange={(event) => setEndsOn(event.target.value)}
        />
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={rollover}
            onChange={(event) => setRollover(event.target.checked)}
          />
          Roll unspent allowance forward (and overspending back)
        </label>
      </form>
    </Modal>
  );
};

export const BudgetsPage = (): JSX.Element => {
  const [period, setPeriod] = useState(currentMonth());
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<BudgetResponse | null>(null);
  const [deleting, setDeleting] = useState<BudgetResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const status = useBudgetStatus(period);
  const budgets = useBudgets();
  const categories = useCategories();
  const remove = useDeleteBudget();

  const categoryNames = new Map(
    (categories.data?.items ?? []).map((category) => [category.id, category.name]),
  );
  const items = status.data?.items ?? [];
  const currencies = new Set(items.map((item) => item.currency));
  const singleCurrency = currencies.size === 1 ? ([...currencies][0] ?? null) : null;
  const totalSpent = items.reduce((sum, item) => sum + item.spent_minor, 0);
  const totalRemaining = items.reduce((sum, item) => sum + item.remaining_minor, 0);
  const overCount = items.filter((item) => item.status === 'over').length;

  const confirmDelete = async (): Promise<void> => {
    if (deleting === null) return;
    setError(null);
    try {
      await remove.mutateAsync(deleting.id);
      setDeleting(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not delete the budget');
    }
  };

  return (
    <div>
      <PageHeader
        title="Budgets"
        description="Monthly limits by category, with optional rollover. Spending includes child categories."
        actions={<Button onClick={() => setFormOpen(true)}>New budget</Button>}
      />

      {error !== null ? <ErrorAlert error={error} /> : null}

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setPeriod(addMonthsToMonth(period, -1))}
          >
            Previous
          </Button>
          <p aria-live="polite" className="min-w-36 text-center text-sm font-medium">
            {monthLabel(period)}
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setPeriod(addMonthsToMonth(period, 1))}
          >
            Next
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setPeriod(currentMonth())}>
            This month
          </Button>
        </div>
      </div>

      {status.error !== null ? <ErrorAlert error={status.error} /> : null}
      {status.isPending ? <LoadingState label="Calculating budget status…" /> : null}

      {!status.isPending ? (
        <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Active budgets" value={String(items.length)} />
          <StatCard
            label="Spent"
            value={
              singleCurrency === null ? 'Mixed currencies' : formatMoney(totalSpent, singleCurrency)
            }
            hint="This month"
          />
          <StatCard
            label="Remaining"
            value={
              singleCurrency === null
                ? 'Mixed currencies'
                : formatMoney(totalRemaining, singleCurrency)
            }
          />
          <StatCard
            label="Over budget"
            value={String(overCount)}
            hint={overCount === 0 ? 'None' : 'Needs attention'}
          />
        </div>
      ) : null}

      {!status.isPending && items.length === 0 ? (
        <EmptyState
          title="No budgets for this month"
          description="Create a monthly limit for the categories you want to track."
          action={<Button onClick={() => setFormOpen(true)}>Create a budget</Button>}
        />
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        {items.map((item) => {
          const budget = (budgets.data?.items ?? []).find(
            (candidate) => candidate.id === item.budget_id,
          );
          return (
            <Card key={item.budget_id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">
                    {categoryNames.get(item.category_id) ?? 'Category'}
                  </h2>
                  <p className="text-xs text-slate-500">
                    {formatMoney(item.spent_minor, item.currency)} of{' '}
                    {formatMoney(item.effective_limit_minor, item.currency)} ·{' '}
                    {formatPercent(item.percent_used)}
                  </p>
                </div>
                <Badge tone={budgetStatusTone(item.status)}>
                  {budgetStatusLabels[item.status]}
                </Badge>
              </div>
              <div className="mt-4">
                <ProgressBar
                  value={Number.parseFloat(item.percent_used)}
                  tone={
                    item.status === 'on_track'
                      ? 'success'
                      : item.status === 'warning'
                        ? 'warning'
                        : 'danger'
                  }
                  label={`${categoryNames.get(item.category_id) ?? 'Budget'} usage`}
                />
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-2 text-xs text-slate-600">
                <div>
                  <dt className="font-medium text-slate-700">Limit</dt>
                  <dd>{formatMoney(item.limit_minor, item.currency)}</dd>
                </div>
                <div>
                  <dt className="font-medium text-slate-700">Rollover in</dt>
                  <dd>{formatMoney(item.rollover_in_minor, item.currency)}</dd>
                </div>
                <div>
                  <dt className="font-medium text-slate-700">Remaining</dt>
                  <dd className={item.remaining_minor < 0 ? 'text-red-700' : ''}>
                    {formatMoney(item.remaining_minor, item.currency)}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-slate-700">Carries forward</dt>
                  <dd>{formatMoney(item.carry_forward_minor, item.currency)}</dd>
                </div>
              </dl>
              {budget !== undefined ? (
                <div className="mt-4 flex justify-end gap-2">
                  <Button variant="ghost" size="sm" onClick={() => setEditing(budget)}>
                    Edit
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setDeleting(budget)}>
                    Delete
                  </Button>
                </div>
              ) : null}
            </Card>
          );
        })}
      </div>

      {formOpen || editing !== null ? (
        <BudgetForm
          budget={editing}
          categories={categories.data?.items ?? []}
          onClose={() => {
            setFormOpen(false);
            setEditing(null);
          }}
        />
      ) : null}

      <ConfirmDialog
        open={deleting !== null}
        title="Delete budget?"
        message="The budget history is removed. Transactions are unaffected."
        onConfirm={() => void confirmDelete()}
        onCancel={() => setDeleting(null)}
        isLoading={remove.isPending}
      />
    </div>
  );
};
