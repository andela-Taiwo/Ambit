import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import {
  useAccounts,
  useBudgetStatus,
  useCategories,
  useNetWorth,
  useTransactions,
} from '@/api/hooks';
import {
  Badge,
  Card,
  EmptyState,
  ErrorAlert,
  LoadingState,
  PageHeader,
  ProgressBar,
  StatCard,
} from '@/components/ui';
import { currentMonth, formatDate, monthLabel } from '@/lib/dates';
import { budgetStatusLabels, budgetStatusTone, transactionTypeLabels } from '@/lib/labels';
import { formatMoney, formatPercent } from '@/lib/money';

export const DashboardPage = (): JSX.Element => {
  const month = currentMonth();
  const netWorth = useNetWorth();
  const budgetStatus = useBudgetStatus(month);
  const transactions = useTransactions({ limit: 5, offset: 0 });
  const accounts = useAccounts();
  const categories = useCategories();

  const accountNames = new Map(
    (accounts.data?.items ?? []).map((account) => [account.id, account.name]),
  );
  const categoryNames = new Map(
    (categories.data?.items ?? []).map((category) => [category.id, category.name]),
  );
  const budgets = budgetStatus.data?.items ?? [];
  const overBudget = budgets.filter((item) => item.status === 'over').length;
  const baseCurrency = netWorth.data?.base_currency ?? 'GBP';

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description={`Your position for ${monthLabel(month)}.`}
        actions={
          <>
            <Link className="text-sm font-medium underline" to="/transactions">
              Add a transaction
            </Link>
            <Link className="text-sm font-medium underline" to="/reports">
              View reports
            </Link>
          </>
        }
      />

      {netWorth.error !== null ? <ErrorAlert error={netWorth.error} /> : null}
      {budgetStatus.error !== null ? <ErrorAlert error={budgetStatus.error} /> : null}

      {netWorth.isPending ? (
        <LoadingState label="Calculating net worth…" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Net worth"
            value={formatMoney(netWorth.data?.total_minor ?? 0, baseCurrency)}
            hint={`As of ${formatDate(netWorth.data?.as_of ?? new Date().toISOString().slice(0, 10))}`}
          />
          <StatCard
            label="Cash accounts"
            value={formatMoney(netWorth.data?.accounts_total_minor ?? 0, baseCurrency)}
            hint={`${String(netWorth.data?.accounts.length ?? 0)} accounts`}
          />
          <StatCard
            label="Investments"
            value={formatMoney(netWorth.data?.investments_total_minor ?? 0, baseCurrency)}
            hint={`${String(netWorth.data?.investments.length ?? 0)} holdings`}
          />
          <StatCard
            label="Budgets over"
            value={String(overBudget)}
            hint={overBudget === 0 ? 'All budgets within limits' : 'Review spending'}
          />
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Budget health</h2>
            <Link className="text-sm underline" to="/budgets">
              Manage
            </Link>
          </div>
          {budgetStatus.isPending ? <LoadingState label="Loading budgets…" /> : null}
          {!budgetStatus.isPending && budgets.length === 0 ? (
            <EmptyState
              title="No budgets yet"
              description="Set a monthly limit to track spending."
            />
          ) : null}
          <ul className="space-y-4">
            {budgets.slice(0, 5).map((item) => (
              <li key={item.budget_id}>
                <div className="mb-1 flex items-center justify-between gap-2">
                  <p className="truncate text-sm font-medium">
                    {categoryNames.get(item.category_id) ?? 'Category'}
                  </p>
                  <Badge tone={budgetStatusTone(item.status)}>
                    {budgetStatusLabels[item.status]}
                  </Badge>
                </div>
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
                <p className="mt-1 text-xs text-slate-600">
                  {formatMoney(item.spent_minor, item.currency)} of{' '}
                  {formatMoney(item.effective_limit_minor, item.currency)} ·{' '}
                  {formatPercent(item.percent_used)}
                </p>
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Recent transactions</h2>
            <Link className="text-sm underline" to="/transactions">
              View all
            </Link>
          </div>
          {transactions.isPending ? <LoadingState label="Loading transactions…" /> : null}
          {!transactions.isPending && (transactions.data?.items.length ?? 0) === 0 ? (
            <EmptyState title="Nothing recorded yet" description="Add your first transaction." />
          ) : null}
          <ul className="divide-y divide-slate-100">
            {(transactions.data?.items ?? []).map((transaction) => (
              <li key={transaction.id} className="flex items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">
                    {transaction.description === '' ? 'Untitled' : transaction.description}
                  </p>
                  <p className="text-xs text-slate-500">
                    {formatDate(transaction.occurred_on)} ·{' '}
                    {accountNames.get(transaction.account_id) ?? 'Account'} ·{' '}
                    {transactionTypeLabels[transaction.transaction_type]}
                  </p>
                </div>
                <p
                  className={`text-sm font-semibold ${
                    transaction.signed_amount_minor < 0 ? 'text-red-700' : 'text-emerald-700'
                  }`}
                >
                  {formatMoney(transaction.signed_amount_minor, transaction.currency)}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
};
