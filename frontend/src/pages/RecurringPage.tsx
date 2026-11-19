import { useState, type SyntheticEvent, type JSX } from 'react';

import {
  useAccounts,
  useCategories,
  useCreateRecurringRule,
  useDeleteRecurringRule,
  useRecurringRules,
  useRunRecurringRule,
  useUpdateRecurringRule,
} from '@/api/hooks';
import type { AccountResponse, CategoryResponse, RecurringRuleResponse } from '@/api/types';
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
import { formatDate, todayIso } from '@/lib/dates';
import { frequencyLabels, transactionTypeLabels } from '@/lib/labels';
import { formatMoney, minorToInput, parseAmountToMinor } from '@/lib/money';

type RuleType = 'income' | 'expense';
type Frequency = 'daily' | 'weekly' | 'monthly' | 'yearly';

const RecurringForm = ({
  rule,
  accounts,
  categories,
  onClose,
}: {
  rule: RecurringRuleResponse | null;
  accounts: AccountResponse[];
  categories: CategoryResponse[];
  onClose: () => void;
}): JSX.Element => {
  const create = useCreateRecurringRule();
  const update = useUpdateRecurringRule();
  const [accountId, setAccountId] = useState(rule?.account_id ?? accounts[0]?.id ?? '');
  const [type, setType] = useState<RuleType>(
    rule?.transaction_type === 'income' ? 'income' : 'expense',
  );
  const account = accounts.find((item) => item.id === accountId);
  const currency = rule?.currency ?? account?.currency ?? 'GBP';
  const [categoryId, setCategoryId] = useState(rule?.category_id ?? '');
  const [amount, setAmount] = useState(
    rule === null ? '' : minorToInput(rule.amount_minor, rule.currency),
  );
  const [description, setDescription] = useState(rule?.description ?? '');
  const [frequency, setFrequency] = useState<Frequency>(rule?.frequency ?? 'monthly');
  const [interval, setInterval] = useState(String(rule?.interval ?? 1));
  const [dayOfMonth, setDayOfMonth] = useState(
    rule?.day_of_month === null ? '' : String(rule?.day_of_month ?? ''),
  );
  const [startsOn, setStartsOn] = useState(rule?.starts_on ?? todayIso());
  const [endsOn, setEndsOn] = useState(rule?.ends_on ?? '');
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const categoryOptions = categories.filter(
    (category) => category.kind === type && !category.is_archived,
  );

  const onSubmit = async (event: SyntheticEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setError(null);
    const nextErrors: Record<string, string> = {};
    const minor = parseAmountToMinor(amount, currency);
    if (accountId === '') nextErrors.account = 'Choose an account';
    if (minor === null || minor <= 0) nextErrors.amount = 'Enter an amount greater than zero';
    if (description.trim() === '') nextErrors.description = 'Add a short description';
    const parsedInterval = Number.parseInt(interval, 10);
    if (!Number.isFinite(parsedInterval) || parsedInterval < 1)
      nextErrors.interval = 'Interval must be at least 1';
    setFieldErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0 || minor === null) return;

    try {
      if (rule === null) {
        await create.mutateAsync({
          account_id: accountId,
          transaction_type: type,
          amount: minorToInput(minor, currency),
          currency,
          description: description.trim(),
          frequency,
          interval: parsedInterval,
          ...(dayOfMonth !== '' ? { day_of_month: Number.parseInt(dayOfMonth, 10) } : {}),
          starts_on: startsOn,
          ...(endsOn !== '' ? { ends_on: endsOn } : {}),
          ...(categoryId !== '' ? { category_id: categoryId } : {}),
        });
      } else {
        await update.mutateAsync({
          id: rule.id,
          body: {
            amount: minorToInput(minor, currency),
            description: description.trim(),
            category_id: categoryId === '' ? null : categoryId,
            ends_on: endsOn === '' ? null : endsOn,
          },
        });
      }
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save the recurring rule');
    }
  };

  return (
    <Modal
      open
      title={rule === null ? 'New recurring rule' : 'Edit recurring rule'}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            form="recurring-form"
            isLoading={create.isPending || update.isPending}
          >
            {rule === null ? 'Create rule' : 'Save changes'}
          </Button>
        </>
      }
    >
      <form
        id="recurring-form"
        className="space-y-4"
        onSubmit={(event) => void onSubmit(event)}
        noValidate
      >
        {error !== null ? <Alert variant="error">{error}</Alert> : null}
        <SelectInput
          label="Account"
          value={accountId}
          disabled={rule !== null}
          {...(fieldErrors.account !== undefined ? { error: fieldErrors.account } : {})}
          onChange={(event) => setAccountId(event.target.value)}
        >
          <option value="">Choose an account</option>
          {accounts.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name} ({item.currency})
            </option>
          ))}
        </SelectInput>
        <SelectInput
          label="Type"
          value={type}
          disabled={rule !== null}
          onChange={(event) => {
            setType(event.target.value as RuleType);
            setCategoryId('');
          }}
        >
          <option value="expense">Expense</option>
          <option value="income">Income</option>
        </SelectInput>
        <TextInput
          label={`Amount (${currency})`}
          inputMode="decimal"
          required
          value={amount}
          {...(fieldErrors.amount !== undefined ? { error: fieldErrors.amount } : {})}
          onChange={(event) => setAmount(event.target.value)}
        />
        <TextInput
          label="Description"
          required
          value={description}
          {...(fieldErrors.description !== undefined ? { error: fieldErrors.description } : {})}
          onChange={(event) => setDescription(event.target.value)}
        />
        <SelectInput
          label="Category"
          value={categoryId}
          onChange={(event) => setCategoryId(event.target.value)}
        >
          <option value="">Uncategorized</option>
          {categoryOptions.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </SelectInput>
        {rule === null ? (
          <>
            <SelectInput
              label="Frequency"
              value={frequency}
              onChange={(event) => setFrequency(event.target.value as Frequency)}
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
              <option value="yearly">Yearly</option>
            </SelectInput>
            <TextInput
              label="Every N periods"
              inputMode="numeric"
              value={interval}
              {...(fieldErrors.interval !== undefined ? { error: fieldErrors.interval } : {})}
              onChange={(event) => setInterval(event.target.value)}
            />
            {frequency === 'monthly' || frequency === 'yearly' ? (
              <TextInput
                label="Day of month (optional)"
                inputMode="numeric"
                value={dayOfMonth}
                hint="Defaults to the start date's day."
                onChange={(event) => setDayOfMonth(event.target.value)}
              />
            ) : null}
            <TextInput
              label="Starts on"
              type="date"
              required
              value={startsOn}
              onChange={(event) => setStartsOn(event.target.value)}
            />
          </>
        ) : (
          <p className="text-xs text-slate-500">
            {frequencyLabels[rule.frequency]} · every {rule.interval} period(s) · next{' '}
            {formatDate(rule.next_run_on)}
          </p>
        )}
        <TextInput
          label="Ends on (optional)"
          type="date"
          value={endsOn}
          onChange={(event) => setEndsOn(event.target.value)}
        />
      </form>
    </Modal>
  );
};

export const RecurringPage = (): JSX.Element => {
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<RecurringRuleResponse | null>(null);
  const [deleting, setDeleting] = useState<RecurringRuleResponse | null>(null);
  const [runResult, setRunResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const rules = useRecurringRules();
  const accounts = useAccounts();
  const categories = useCategories();
  const update = useUpdateRecurringRule();
  const remove = useDeleteRecurringRule();
  const run = useRunRecurringRule();

  const accountNames = new Map((accounts.data?.items ?? []).map((item) => [item.id, item.name]));
  const categoryNames = new Map((categories.data?.items ?? []).map((item) => [item.id, item.name]));

  const toggleActive = async (rule: RecurringRuleResponse): Promise<void> => {
    setError(null);
    try {
      await update.mutateAsync({ id: rule.id, body: { is_active: !rule.is_active } });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not update the rule');
    }
  };

  const runNow = async (rule: RecurringRuleResponse): Promise<void> => {
    setError(null);
    setRunResult(null);
    try {
      const result = await run.mutateAsync({ id: rule.id });
      setRunResult(
        `${rule.description === '' ? 'Rule' : rule.description}: ${String(result.generated_count)} generated, ${String(result.skipped_count)} skipped. Next ${formatDate(result.next_run_on)}.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not run the rule');
    }
  };

  const confirmDelete = async (): Promise<void> => {
    if (deleting === null) return;
    try {
      await remove.mutateAsync(deleting.id);
      setDeleting(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not delete the rule');
    }
  };

  const items = rules.data?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Recurring"
        description="Rent, salary and subscriptions generated on a schedule. Generation is idempotent per occurrence."
        actions={<Button onClick={() => setFormOpen(true)}>New recurring rule</Button>}
      />

      {error !== null ? <ErrorAlert error={error} /> : null}
      {runResult !== null ? <Alert variant="success">{runResult}</Alert> : null}

      {rules.error !== null ? <ErrorAlert error={rules.error} /> : null}
      {rules.isPending ? <LoadingState label="Loading recurring rules…" /> : null}

      {!rules.isPending && items.length === 0 ? (
        <EmptyState
          title="No recurring rules"
          description="Automate the transactions that happen every week, month or year."
          action={<Button onClick={() => setFormOpen(true)}>Create a rule</Button>}
        />
      ) : null}

      {items.length > 0 ? (
        <Card className="overflow-x-auto p-0">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th scope="col" className="px-4 py-3 text-left font-medium text-slate-600">
                  Description
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium text-slate-600">
                  Account
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium text-slate-600">
                  Category
                </th>
                <th scope="col" className="px-4 py-3 text-right font-medium text-slate-600">
                  Amount
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium text-slate-600">
                  Schedule
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium text-slate-600">
                  Next
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
              {items.map((rule) => (
                <tr key={rule.id}>
                  <td className="px-4 py-3 font-medium">
                    {rule.description}
                    <span className="block text-xs text-slate-500">
                      {transactionTypeLabels[rule.transaction_type]}
                    </span>
                  </td>
                  <td className="px-4 py-3">{accountNames.get(rule.account_id) ?? '—'}</td>
                  <td className="px-4 py-3">
                    {rule.category_id === null
                      ? 'Uncategorized'
                      : (categoryNames.get(rule.category_id) ?? '—')}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {formatMoney(rule.amount_minor, rule.currency)}
                  </td>
                  <td className="px-4 py-3">
                    {frequencyLabels[rule.frequency]} · every {rule.interval}
                  </td>
                  <td className="px-4 py-3">{formatDate(rule.next_run_on)}</td>
                  <td className="px-4 py-3">
                    {rule.is_active ? (
                      <Badge tone="success">Active</Badge>
                    ) : (
                      <Badge tone="neutral">Paused</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" size="sm" onClick={() => void runNow(rule)}>
                        Run now
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => void toggleActive(rule)}>
                        {rule.is_active ? 'Pause' : 'Resume'}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setEditing(rule)}>
                        Edit
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setDeleting(rule)}>
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
        <RecurringForm
          rule={editing}
          accounts={accounts.data?.items ?? []}
          categories={categories.data?.items ?? []}
          onClose={() => {
            setFormOpen(false);
            setEditing(null);
          }}
        />
      ) : null}

      <ConfirmDialog
        open={deleting !== null}
        title="Delete recurring rule?"
        message="Generated transactions remain. Future occurrences stop."
        onConfirm={() => void confirmDelete()}
        onCancel={() => setDeleting(null)}
        isLoading={remove.isPending}
      />
    </div>
  );
};
