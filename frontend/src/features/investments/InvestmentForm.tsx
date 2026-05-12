import { useMemo, useState, type SyntheticEvent, type JSX } from 'react';

import { useCreateInvestment, useUpdateInvestment } from '@/api/hooks';
import type { AccountResponse, InvestmentResponse, InvestmentType, RatePeriod } from '@/api/types';
import { Alert, Button, Modal, SelectInput, TextAreaInput, TextInput } from '@/components/ui';
import { todayIso } from '@/lib/dates';
import { formatMoney, minorToInput, parseAmountToMinor } from '@/lib/money';

export const InvestmentForm = ({
  investment,
  accounts,
  onClose,
}: {
  investment: InvestmentResponse | null;
  accounts: AccountResponse[];
  onClose: () => void;
}): JSX.Element => {
  const create = useCreateInvestment();
  const update = useUpdateInvestment();
  const investmentAccounts = accounts.filter(
    (account) => account.account_type === 'investment' && !account.is_archived,
  );
  const initialAccount = investment?.account_id ?? investmentAccounts[0]?.id ?? '';
  const [accountId, setAccountId] = useState(initialAccount);
  const account = investmentAccounts.find((item) => item.id === accountId);
  const currency = investment?.currency ?? account?.currency ?? 'GBP';
  const [name, setName] = useState(investment?.name ?? '');
  const [type, setType] = useState<InvestmentType>(investment?.investment_type ?? 'fixed_rate');
  const [principal, setPrincipal] = useState(
    investment === null ? '' : minorToInput(investment.principal_minor, investment.currency),
  );
  const [rate, setRate] = useState(investment?.rate ?? '');
  const [ratePeriod, setRatePeriod] = useState<RatePeriod>(investment?.rate_period ?? 'annual');
  const [compounding, setCompounding] = useState<'simple' | 'monthly'>(
    investment?.compounding ?? 'simple',
  );
  const [startDate, setStartDate] = useState(investment?.start_date ?? todayIso());
  const [maturityDate, setMaturityDate] = useState(investment?.maturity_date ?? '');
  const [notes, setNotes] = useState(investment?.notes ?? '');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const fixed = type === 'fixed_rate';
  const accountOptions = useMemo(() => investmentAccounts, [investmentAccounts]);

  const onSubmit = async (event: SyntheticEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setError(null);
    const nextErrors: Record<string, string> = {};
    if (name.trim() === '') nextErrors.name = 'Enter a name';
    if (accountId === '') nextErrors.account = 'Choose an investment account';
    const principalMinor = parseAmountToMinor(principal, currency);
    if (principalMinor === null) nextErrors.principal = 'Enter a valid principal';
    if (fixed && (rate.trim() === '' || Number(rate) <= 0))
      nextErrors.rate = 'Enter a positive rate';
    if (maturityDate !== '' && maturityDate < startDate) {
      nextErrors.maturity = 'Maturity cannot be before the start date';
    }
    setFieldErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0 || principalMinor === null) return;

    try {
      if (investment === null) {
        await create.mutateAsync({
          account_id: accountId,
          name: name.trim(),
          investment_type: type,
          principal: minorToInput(principalMinor, currency),
          currency,
          compounding,
          start_date: startDate,
          ...(maturityDate !== '' ? { maturity_date: maturityDate } : {}),
          ...(fixed ? { rate, rate_period: ratePeriod } : {}),
          ...(notes.trim() !== '' ? { notes: notes.trim() } : {}),
        });
      } else {
        await update.mutateAsync({
          id: investment.id,
          body: {
            name: name.trim(),
            principal: minorToInput(principalMinor, currency),
            compounding,
            maturity_date: maturityDate === '' ? null : maturityDate,
            notes: notes.trim() === '' ? null : notes.trim(),
            ...(fixed ? { rate, rate_period: ratePeriod } : {}),
          },
        });
      }
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save the investment');
    }
  };

  return (
    <Modal
      open
      title={investment === null ? 'New investment' : 'Edit investment'}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            form="investment-form"
            isLoading={create.isPending || update.isPending}
          >
            {investment === null ? 'Create investment' : 'Save changes'}
          </Button>
        </>
      }
    >
      <form
        id="investment-form"
        className="space-y-4"
        onSubmit={(event) => void onSubmit(event)}
        noValidate
      >
        {error !== null ? <Alert variant="error">{error}</Alert> : null}
        <SelectInput
          label="Investment account"
          value={accountId}
          disabled={investment !== null}
          {...(fieldErrors.account !== undefined ? { error: fieldErrors.account } : {})}
          onChange={(event) => setAccountId(event.target.value)}
        >
          <option value="">Choose an investment account</option>
          {accountOptions.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name} ({item.currency})
            </option>
          ))}
        </SelectInput>
        {investmentAccounts.length === 0 ? (
          <Alert variant="info">Create an investment account first on the Accounts page.</Alert>
        ) : null}
        <TextInput
          label="Name"
          required
          value={name}
          {...(fieldErrors.name !== undefined ? { error: fieldErrors.name } : {})}
          onChange={(event) => setName(event.target.value)}
        />
        <SelectInput
          label="Type"
          value={type}
          disabled={investment !== null}
          onChange={(event) => setType(event.target.value as InvestmentType)}
        >
          <option value="fixed_rate">Fixed rate</option>
          <option value="market_priced">Market priced</option>
        </SelectInput>
        <TextInput
          label={`Principal (${currency})`}
          inputMode="decimal"
          required
          value={principal}
          {...(fieldErrors.principal !== undefined ? { error: fieldErrors.principal } : {})}
          onChange={(event) => setPrincipal(event.target.value)}
        />
        {principal !== '' && parseAmountToMinor(principal, currency) !== null ? (
          <p className="text-xs text-slate-500">
            Cost basis {formatMoney(parseAmountToMinor(principal, currency) ?? 0, currency)}
          </p>
        ) : null}
        {fixed ? (
          <>
            <TextInput
              label="Rate (%)"
              inputMode="decimal"
              required
              value={rate}
              {...(fieldErrors.rate !== undefined ? { error: fieldErrors.rate } : {})}
              onChange={(event) => setRate(event.target.value)}
            />
            <SelectInput
              label="Rate period"
              value={ratePeriod}
              onChange={(event) => setRatePeriod(event.target.value as RatePeriod)}
            >
              <option value="annual">Per year</option>
              <option value="monthly">Per month</option>
            </SelectInput>
            <SelectInput
              label="Compounding"
              value={compounding}
              onChange={(event) => setCompounding(event.target.value as 'simple' | 'monthly')}
            >
              <option value="simple">Simple interest</option>
              <option value="monthly">Monthly compounding</option>
            </SelectInput>
          </>
        ) : (
          <p className="text-xs text-slate-500">
            Market-priced holdings are valued from snapshots; without one they are shown at cost.
          </p>
        )}
        <TextInput
          label="Start date"
          type="date"
          required
          disabled={investment !== null}
          value={startDate}
          onChange={(event) => setStartDate(event.target.value)}
        />
        <TextInput
          label="Maturity date (optional)"
          type="date"
          value={maturityDate}
          {...(fieldErrors.maturity !== undefined ? { error: fieldErrors.maturity } : {})}
          onChange={(event) => setMaturityDate(event.target.value)}
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
