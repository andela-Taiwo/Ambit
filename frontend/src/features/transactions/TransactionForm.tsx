import { useMemo, useState, type SyntheticEvent, type JSX } from 'react';

import { useCreateTransaction, useUpdateTransaction } from '@/api/hooks';
import type { AccountResponse, CategoryResponse, TransactionResponse } from '@/api/types';
import { Alert, Button, Modal, SelectInput, TextAreaInput, TextInput } from '@/components/ui';
import { todayIso } from '@/lib/dates';
import { formatMoney, minorToInput, parseAmountToMinor } from '@/lib/money';

type EditableType = 'income' | 'expense';

export const TransactionForm = ({
  transaction,
  accounts,
  categories,
  onClose,
}: {
  transaction: TransactionResponse | null;
  accounts: AccountResponse[];
  categories: CategoryResponse[];
  onClose: () => void;
}): JSX.Element => {
  const create = useCreateTransaction();
  const update = useUpdateTransaction();
  const initialAccount = transaction?.account_id ?? accounts[0]?.id ?? '';
  const initialType: EditableType =
    transaction?.transaction_type === 'income' ? 'income' : 'expense';

  const [accountId, setAccountId] = useState(initialAccount);
  const [type, setType] = useState<EditableType>(initialType);
  const [amount, setAmount] = useState(
    transaction === null ? '' : minorToInput(transaction.amount_minor, transaction.currency),
  );
  const [categoryId, setCategoryId] = useState(transaction?.category_id ?? '');
  const [occurredOn, setOccurredOn] = useState(transaction?.occurred_on ?? todayIso());
  const [description, setDescription] = useState(transaction?.description ?? '');
  const [notes, setNotes] = useState(transaction?.notes ?? '');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const account = accounts.find((item) => item.id === accountId);
  const currency = transaction?.currency ?? account?.currency ?? 'GBP';
  const categoryOptions = useMemo(
    () => categories.filter((category) => category.kind === type && !category.is_archived),
    [categories, type],
  );

  const onSubmit = async (event: SyntheticEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setError(null);
    const nextErrors: Record<string, string> = {};
    if (accountId === '') nextErrors.account = 'Choose an account';
    const minor = parseAmountToMinor(amount, currency);
    if (minor === null || minor <= 0) nextErrors.amount = 'Enter an amount greater than zero';
    if (occurredOn === '') nextErrors.occurred_on = 'Choose a date';
    setFieldErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0 || minor === null) return;

    try {
      if (transaction === null) {
        await create.mutateAsync({
          account_id: accountId,
          transaction_type: type,
          amount: minorToInput(minor, currency),
          currency,
          occurred_on: occurredOn,
          description: description.trim(),
          ...(categoryId !== '' ? { category_id: categoryId } : {}),
          ...(notes.trim() !== '' ? { notes: notes.trim() } : {}),
        });
      } else {
        await update.mutateAsync({
          id: transaction.id,
          body: {
            amount: minorToInput(minor, currency),
            category_id: categoryId === '' ? null : categoryId,
            occurred_on: occurredOn,
            description: description.trim(),
            notes: notes.trim() === '' ? null : notes.trim(),
          },
        });
      }
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save the transaction');
    }
  };

  return (
    <Modal
      open
      title={transaction === null ? 'New transaction' : 'Edit transaction'}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            form="transaction-form"
            isLoading={create.isPending || update.isPending}
          >
            {transaction === null ? 'Add transaction' : 'Save changes'}
          </Button>
        </>
      }
    >
      <form
        id="transaction-form"
        className="space-y-4"
        onSubmit={(event) => void onSubmit(event)}
        noValidate
      >
        {error !== null ? <Alert variant="error">{error}</Alert> : null}
        <SelectInput
          label="Account"
          value={accountId}
          disabled={transaction !== null}
          {...(fieldErrors.account !== undefined ? { error: fieldErrors.account } : {})}
          onChange={(event) => {
            setAccountId(event.target.value);
            setCategoryId('');
          }}
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
          disabled={transaction !== null}
          onChange={(event) => {
            setType(event.target.value as EditableType);
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
        {account !== undefined && amount !== '' ? (
          <p className="text-xs text-slate-500">
            Stored as {formatMoney(parseAmountToMinor(amount, currency) ?? 0, currency)}
          </p>
        ) : null}

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

        <TextInput
          label="Date"
          type="date"
          required
          value={occurredOn}
          {...(fieldErrors.occurred_on !== undefined ? { error: fieldErrors.occurred_on } : {})}
          onChange={(event) => setOccurredOn(event.target.value)}
        />
        <TextInput
          label="Description"
          value={description}
          maxLength={255}
          onChange={(event) => setDescription(event.target.value)}
        />
        <TextAreaInput
          label="Notes"
          rows={3}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
        />
      </form>
    </Modal>
  );
};
