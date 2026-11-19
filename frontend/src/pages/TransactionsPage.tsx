import { useState, type JSX } from 'react';

import { useAccounts, useCategories, useDeleteTransaction, useTransactions } from '@/api/hooks';
import type { TransactionFilters } from '@/api/endpoints';
import type { TransactionResponse } from '@/api/types';
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorAlert,
  LoadingState,
  PageHeader,
  Pagination,
  SelectInput,
} from '@/components/ui';
import { ImportDialog } from '@/features/transactions/ImportDialog';
import { TransactionForm } from '@/features/transactions/TransactionForm';
import { TransferForm } from '@/features/transactions/TransferForm';
import { formatDate } from '@/lib/dates';
import { transactionTypeLabels } from '@/lib/labels';
import { formatMoney } from '@/lib/money';

const LIMIT = 50;

export const TransactionsPage = (): JSX.Element => {
  const [accountId, setAccountId] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [type, setType] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [offset, setOffset] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<TransactionResponse | null>(null);
  const [transferOpen, setTransferOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [deleting, setDeleting] = useState<TransactionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const filters: TransactionFilters = {
    limit: LIMIT,
    offset,
    ...(accountId !== '' ? { account_id: accountId } : {}),
    ...(categoryId !== '' ? { category_id: categoryId } : {}),
    ...(type !== '' ? { transaction_type: type } : {}),
    ...(dateFrom !== '' ? { date_from: dateFrom } : {}),
    ...(dateTo !== '' ? { date_to: dateTo } : {}),
  };

  const transactions = useTransactions(filters);
  const accounts = useAccounts();
  const categories = useCategories();
  const remove = useDeleteTransaction();

  const accountList = accounts.data?.items ?? [];
  const categoryList = categories.data?.items ?? [];
  const accountNames = new Map(accountList.map((account) => [account.id, account.name]));
  const categoryNames = new Map(categoryList.map((category) => [category.id, category.name]));

  const resetFilters = (): void => {
    setAccountId('');
    setCategoryId('');
    setType('');
    setDateFrom('');
    setDateTo('');
    setOffset(0);
  };

  const confirmDelete = async (): Promise<void> => {
    if (deleting === null) return;
    setError(null);
    try {
      await remove.mutateAsync(deleting.id);
      setDeleting(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not delete the transaction');
    }
  };

  return (
    <div>
      <PageHeader
        title="Transactions"
        description="Every income, expense and transfer, ordered by date."
        actions={
          <>
            <Button variant="secondary" onClick={() => setImportOpen(true)}>
              Import CSV
            </Button>
            <Button variant="secondary" onClick={() => setTransferOpen(true)}>
              Transfer
            </Button>
            <Button onClick={() => setFormOpen(true)}>New transaction</Button>
          </>
        }
      />

      {error !== null ? <ErrorAlert error={error} /> : null}

      <Card className="mb-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <SelectInput
            label="Account"
            value={accountId}
            onChange={(event) => {
              setAccountId(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">All accounts</option>
            {accountList.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name}
              </option>
            ))}
          </SelectInput>
          <SelectInput
            label="Category"
            value={categoryId}
            onChange={(event) => {
              setCategoryId(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">All categories</option>
            {categoryList.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </SelectInput>
          <SelectInput
            label="Type"
            value={type}
            onChange={(event) => {
              setType(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">All types</option>
            <option value="income">Income</option>
            <option value="expense">Expense</option>
            <option value="transfer">Transfer</option>
          </SelectInput>
          <label className="space-y-1 text-sm">
            <span className="block font-medium text-slate-700">From</span>
            <input
              type="date"
              value={dateFrom}
              onChange={(event) => {
                setDateFrom(event.target.value);
                setOffset(0);
              }}
              className="block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="block font-medium text-slate-700">To</span>
            <input
              type="date"
              value={dateTo}
              onChange={(event) => {
                setDateTo(event.target.value);
                setOffset(0);
              }}
              className="block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
        </div>
        <div className="mt-3 flex justify-end">
          <Button variant="ghost" size="sm" onClick={resetFilters}>
            Clear filters
          </Button>
        </div>
      </Card>

      {transactions.error !== null ? <ErrorAlert error={transactions.error} /> : null}
      {transactions.isPending ? <LoadingState label="Loading transactions…" /> : null}

      {!transactions.isPending && (transactions.data?.total ?? 0) === 0 ? (
        <EmptyState
          title="No transactions match"
          description="Adjust the filters or record a new transaction."
          action={<Button onClick={() => setFormOpen(true)}>Add a transaction</Button>}
        />
      ) : null}

      {(transactions.data?.total ?? 0) > 0 ? (
        <Card className="overflow-x-auto p-0">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th scope="col" className="px-4 py-3 text-left font-medium text-slate-600">
                  Date
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium text-slate-600">
                  Description
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium text-slate-600">
                  Account
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium text-slate-600">
                  Category
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium text-slate-600">
                  Type
                </th>
                <th scope="col" className="px-4 py-3 text-right font-medium text-slate-600">
                  Amount
                </th>
                <th scope="col" className="px-4 py-3 text-right font-medium text-slate-600">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(transactions.data?.items ?? []).map((transaction) => (
                <tr key={transaction.id}>
                  <td className="whitespace-nowrap px-4 py-3">
                    {formatDate(transaction.occurred_on)}
                  </td>
                  <td className="max-w-xs truncate px-4 py-3">
                    {transaction.description === '' ? '—' : transaction.description}
                    {transaction.transfer_group_id !== null ? (
                      <Badge tone="info">
                        <span className="ml-2">Transfer</span>
                      </Badge>
                    ) : null}
                  </td>
                  <td className="px-4 py-3">{accountNames.get(transaction.account_id) ?? '—'}</td>
                  <td className="px-4 py-3">
                    {transaction.category_id === null
                      ? 'Uncategorized'
                      : (categoryNames.get(transaction.category_id) ?? '—')}
                  </td>
                  <td className="px-4 py-3">
                    {transactionTypeLabels[transaction.transaction_type]}
                  </td>
                  <td
                    className={`whitespace-nowrap px-4 py-3 text-right font-medium ${
                      transaction.signed_amount_minor < 0 ? 'text-red-700' : 'text-emerald-700'
                    }`}
                  >
                    {formatMoney(transaction.signed_amount_minor, transaction.currency)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={transaction.transfer_group_id !== null}
                        onClick={() => setEditing(transaction)}
                      >
                        Edit
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setDeleting(transaction)}>
                        Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="border-t border-slate-200 px-4">
            <Pagination
              total={transactions.data?.total ?? 0}
              limit={LIMIT}
              offset={offset}
              onChange={setOffset}
            />
          </div>
        </Card>
      ) : null}

      {formOpen || editing !== null ? (
        <TransactionForm
          transaction={editing}
          accounts={accountList}
          categories={categoryList}
          onClose={() => {
            setFormOpen(false);
            setEditing(null);
          }}
        />
      ) : null}

      {transferOpen ? (
        <TransferForm accounts={accountList} onClose={() => setTransferOpen(false)} />
      ) : null}

      {importOpen ? (
        <ImportDialog
          accounts={accountList}
          categories={categoryList}
          onClose={() => setImportOpen(false)}
        />
      ) : null}

      <ConfirmDialog
        open={deleting !== null}
        title="Delete transaction?"
        message={
          deleting?.transfer_group_id !== null && deleting !== null
            ? 'This deletes both legs of the transfer. This cannot be undone.'
            : 'This cannot be undone.'
        }
        onConfirm={() => void confirmDelete()}
        onCancel={() => setDeleting(null)}
        isLoading={remove.isPending}
      />
    </div>
  );
};
