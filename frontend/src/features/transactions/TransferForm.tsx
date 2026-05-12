import { useMemo, useState, type SyntheticEvent, type JSX } from 'react';

import { useCreateTransfer } from '@/api/hooks';
import type { AccountResponse } from '@/api/types';
import { Alert, Button, Modal, SelectInput, TextAreaInput, TextInput } from '@/components/ui';
import { todayIso } from '@/lib/dates';
import { minorToInput, parseAmountToMinor } from '@/lib/money';

export const TransferForm = ({
  accounts,
  onClose,
}: {
  accounts: AccountResponse[];
  onClose: () => void;
}): JSX.Element => {
  const create = useCreateTransfer();
  const [fromId, setFromId] = useState(accounts[0]?.id ?? '');
  const from = accounts.find((account) => account.id === fromId);
  const destinations = useMemo(
    () =>
      accounts.filter((account) => account.id !== fromId && account.currency === from?.currency),
    [accounts, fromId, from?.currency],
  );
  const [toId, setToId] = useState(destinations[0]?.id ?? '');
  const [amount, setAmount] = useState('');
  const [occurredOn, setOccurredOn] = useState(todayIso());
  const [description, setDescription] = useState('');
  const [notes, setNotes] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const currency = from?.currency ?? 'GBP';

  const onSubmit = async (event: SyntheticEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setError(null);
    const nextErrors: Record<string, string> = {};
    const minor = parseAmountToMinor(amount, currency);
    if (minor === null || minor <= 0) nextErrors.amount = 'Enter an amount greater than zero';
    if (fromId === '') nextErrors.from_account = 'Choose a source account';
    if (toId === '') nextErrors.to_account = 'Choose a destination account';
    if (fromId === toId) nextErrors.to_account = 'Choose a different destination account';
    setFieldErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0 || minor === null) return;

    try {
      await create.mutateAsync({
        from_account_id: fromId,
        to_account_id: toId,
        amount: minorToInput(minor, currency),
        currency,
        occurred_on: occurredOn,
        description: description.trim(),
        ...(notes.trim() !== '' ? { notes: notes.trim() } : {}),
      });
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not create the transfer');
    }
  };

  return (
    <Modal
      open
      title="Transfer between accounts"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="transfer-form" isLoading={create.isPending}>
            Create transfer
          </Button>
        </>
      }
    >
      <form
        id="transfer-form"
        className="space-y-4"
        onSubmit={(event) => void onSubmit(event)}
        noValidate
      >
        {error !== null ? <Alert variant="error">{error}</Alert> : null}
        <SelectInput
          label="From account"
          value={fromId}
          {...(fieldErrors.from_account !== undefined ? { error: fieldErrors.from_account } : {})}
          onChange={(event) => {
            setFromId(event.target.value);
            setToId('');
          }}
        >
          <option value="">Choose an account</option>
          {accounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name} ({account.currency})
            </option>
          ))}
        </SelectInput>
        <SelectInput
          label="To account"
          value={toId}
          {...(fieldErrors.to_account !== undefined ? { error: fieldErrors.to_account } : {})}
          onChange={(event) => setToId(event.target.value)}
        >
          <option value="">Choose an account</option>
          {destinations.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name} ({account.currency})
            </option>
          ))}
        </SelectInput>
        <p className="text-xs text-slate-500">
          Only accounts in the same currency are listed; cross-currency transfers require an
          exchange rate and are not supported yet.
        </p>
        <TextInput
          label={`Amount (${currency})`}
          inputMode="decimal"
          required
          value={amount}
          {...(fieldErrors.amount !== undefined ? { error: fieldErrors.amount } : {})}
          onChange={(event) => setAmount(event.target.value)}
        />
        <TextInput
          label="Date"
          type="date"
          required
          value={occurredOn}
          onChange={(event) => setOccurredOn(event.target.value)}
        />
        <TextInput
          label="Description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
        <TextAreaInput
          label="Notes"
          rows={2}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
        />
      </form>
    </Modal>
  );
};
