import { useState, type SyntheticEvent, type JSX } from 'react';

import {
  useAccountBalances,
  useAccounts,
  useCreateAccount,
  useDeleteAccount,
  useUpdateAccount,
} from '@/api/hooks';
import type { AccountResponse, AccountType } from '@/api/types';
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
import { accountTypeLabels } from '@/lib/labels';
import { SUPPORTED_CURRENCIES, formatMoney, minorToInput, parseAmountToMinor } from '@/lib/money';

const accountTypes = Object.keys(accountTypeLabels) as AccountType[];

const AccountForm = ({
  account,
  onClose,
}: {
  account: AccountResponse | null;
  onClose: () => void;
}): JSX.Element => {
  const create = useCreateAccount();
  const update = useUpdateAccount();
  const [name, setName] = useState(account?.name ?? '');
  const [accountType, setAccountType] = useState<AccountType>(account?.account_type ?? 'current');
  const [currency, setCurrency] = useState(account?.currency ?? 'GBP');
  const [openingBalance, setOpeningBalance] = useState(
    account === null ? '0.00' : minorToInput(account.opening_balance_minor, account.currency),
  );
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [openingError, setOpeningError] = useState<string | null>(null);

  const onSubmit = async (event: SyntheticEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setError(null);
    if (name.trim() === '') {
      setFieldError('Enter an account name');
      return;
    }
    setFieldError(null);

    try {
      if (account === null) {
        const minor = parseAmountToMinor(openingBalance, currency);
        if (minor === null) {
          setOpeningError('Enter a valid opening balance');
          return;
        }
        await create.mutateAsync({
          name: name.trim(),
          account_type: accountType,
          currency,
          opening_balance: minorToInput(minor, currency),
        });
      } else {
        await update.mutateAsync({
          id: account.id,
          body: { name: name.trim(), account_type: accountType },
        });
      }
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save the account');
    }
  };

  return (
    <Modal
      open
      title={account === null ? 'New account' : 'Edit account'}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            form="account-form"
            isLoading={create.isPending || update.isPending}
          >
            {account === null ? 'Create account' : 'Save changes'}
          </Button>
        </>
      }
    >
      <form
        id="account-form"
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
        <SelectInput
          label="Type"
          value={accountType}
          onChange={(event) => setAccountType(event.target.value as AccountType)}
        >
          {accountTypes.map((type) => (
            <option key={type} value={type}>
              {accountTypeLabels[type]}
            </option>
          ))}
        </SelectInput>
        {account === null ? (
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
              label="Opening balance"
              inputMode="decimal"
              hint="Use a negative value for a credit card or overdraft."
              value={openingBalance}
              {...(openingError !== null ? { error: openingError } : {})}
              onChange={(event) => setOpeningBalance(event.target.value)}
            />
          </>
        ) : (
          <p className="text-xs text-slate-500">Currency is fixed after creation.</p>
        )}
      </form>
    </Modal>
  );
};

export const AccountsPage = (): JSX.Element => {
  const [includeArchived, setIncludeArchived] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<AccountResponse | null>(null);
  const [deleting, setDeleting] = useState<AccountResponse | null>(null);
  const accounts = useAccounts(includeArchived);
  const balances = useAccountBalances((accounts.data?.items ?? []).map((account) => account.id));
  const update = useUpdateAccount();
  const remove = useDeleteAccount();
  const [error, setError] = useState<string | null>(null);

  const toggleArchive = async (account: AccountResponse): Promise<void> => {
    setError(null);
    try {
      await update.mutateAsync({
        id: account.id,
        body: { is_archived: !account.is_archived },
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not update the account');
    }
  };

  const confirmDelete = async (): Promise<void> => {
    if (deleting === null) return;
    setError(null);
    try {
      await remove.mutateAsync(deleting.id);
      setDeleting(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not delete the account');
    }
  };

  return (
    <div>
      <PageHeader
        title="Accounts"
        description="Cash, bank and investment containers. Balances include every recorded movement."
        actions={<Button onClick={() => setFormOpen(true)}>New account</Button>}
      />

      {error !== null ? <ErrorAlert error={error} /> : null}
      <div className="mb-4 flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(event) => setIncludeArchived(event.target.checked)}
          />
          Show archived accounts
        </label>
        {accounts.isFetching ? <span className="text-xs text-slate-500">Refreshing…</span> : null}
      </div>

      {accounts.error !== null ? <ErrorAlert error={accounts.error} /> : null}
      {accounts.isPending ? <LoadingState label="Loading accounts…" /> : null}

      {!accounts.isPending && (accounts.data?.items.length ?? 0) === 0 ? (
        <EmptyState
          title="No accounts yet"
          description="Create a current account or savings account to start recording transactions."
          action={<Button onClick={() => setFormOpen(true)}>Create your first account</Button>}
        />
      ) : null}

      {(accounts.data?.items.length ?? 0) > 0 ? (
        <Card className="overflow-x-auto p-0">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th scope="col" className="px-4 py-3 text-left font-medium text-slate-600">
                  Name
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium text-slate-600">
                  Type
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium text-slate-600">
                  Currency
                </th>
                <th scope="col" className="px-4 py-3 text-right font-medium text-slate-600">
                  Balance
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
              {(accounts.data?.items ?? []).map((account) => {
                const balance = balances[account.id];
                return (
                  <tr key={account.id}>
                    <td className="px-4 py-3 font-medium">{account.name}</td>
                    <td className="px-4 py-3">{accountTypeLabels[account.account_type]}</td>
                    <td className="px-4 py-3">{account.currency}</td>
                    <td className="px-4 py-3 text-right">
                      {balance === undefined
                        ? '…'
                        : formatMoney(balance.balance_minor, balance.currency)}
                    </td>
                    <td className="px-4 py-3">
                      {account.is_archived ? (
                        <Badge tone="neutral">Archived</Badge>
                      ) : (
                        <Badge tone="success">Active</Badge>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => setEditing(account)}>
                          Edit
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void toggleArchive(account)}
                        >
                          {account.is_archived ? 'Restore' : 'Archive'}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setDeleting(account)}>
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      ) : null}

      {formOpen || editing !== null ? (
        <AccountForm
          account={editing}
          onClose={() => {
            setFormOpen(false);
            setEditing(null);
          }}
        />
      ) : null}

      <ConfirmDialog
        open={deleting !== null}
        title="Delete account?"
        message="This also deletes every transaction in the account. This cannot be undone."
        onConfirm={() => void confirmDelete()}
        onCancel={() => setDeleting(null)}
        isLoading={remove.isPending}
      />
    </div>
  );
};
