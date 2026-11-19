import { useState, type SyntheticEvent, type JSX } from 'react';

import {
  useCreateValuation,
  useDeleteValuation,
  useInvestmentReturns,
  useValuations,
} from '@/api/hooks';
import type { InvestmentResponse, ValuationResponse } from '@/api/types';
import {
  Alert,
  Badge,
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorAlert,
  LoadingState,
  Modal,
  StatCard,
  TextAreaInput,
  TextInput,
} from '@/components/ui';
import { todayIso } from '@/lib/dates';
import { valueSourceLabels } from '@/lib/labels';
import { formatMoney, formatPercent, parseAmountToMinor, minorToInput } from '@/lib/money';

export const InvestmentDetail = ({
  investment,
  onClose,
  onEdit,
}: {
  investment: InvestmentResponse;
  onClose: () => void;
  onEdit: () => void;
}): JSX.Element => {
  const returns = useInvestmentReturns(investment.id);
  const valuations = useValuations(investment.id);
  const createValuation = useCreateValuation();
  const deleteValuation = useDeleteValuation();
  const [asOf, setAsOf] = useState(todayIso());
  const [value, setValue] = useState('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<ValuationResponse | null>(null);

  const onCreateValuation = async (event: SyntheticEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setError(null);
    const minor = parseAmountToMinor(value, investment.currency);
    if (minor === null) {
      setFieldError('Enter a valid valuation');
      return;
    }
    setFieldError(null);
    try {
      await createValuation.mutateAsync({
        id: investment.id,
        body: {
          as_of: asOf,
          value: minorToInput(minor, investment.currency),
          ...(notes.trim() !== '' ? { notes: notes.trim() } : {}),
        },
      });
      setValue('');
      setNotes('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not record the valuation');
    }
  };

  const onDeleteValuation = async (): Promise<void> => {
    if (deleting === null) return;
    try {
      await deleteValuation.mutateAsync({ id: investment.id, valuationId: deleting.id });
      setDeleting(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not delete the valuation');
    }
  };

  const data = returns.data;

  return (
    <Modal
      open
      title={investment.name}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onEdit}>
            Edit investment
          </Button>
          <Button onClick={onClose}>Close</Button>
        </>
      }
    >
      {returns.error !== null ? <ErrorAlert error={returns.error} /> : null}
      {returns.isPending ? <LoadingState label="Valuing investment…" /> : null}

      {data !== undefined ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <StatCard label="Current value" value={formatMoney(data.value_minor, data.currency)} />
            <StatCard
              label="Gain"
              value={formatMoney(data.gain_minor, data.currency)}
              hint={formatPercent(data.gain_percent)}
            />
            <StatCard
              label="Accrued interest"
              value={formatMoney(data.accrued_interest_minor, data.currency)}
              {...(data.value_source === 'accrual' ? { hint: 'No snapshot yet' } : {})}
            />
            <StatCard
              label="Projected monthly"
              value={
                data.projected_monthly_interest_minor === null
                  ? '—'
                  : formatMoney(data.projected_monthly_interest_minor, data.currency)
              }
            />
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
            <Badge tone="info">{valueSourceLabels[data.value_source]}</Badge>
            {data.valuation_as_of !== null ? <span>Valued {data.valuation_as_of}</span> : null}
            <span>
              Cost {formatMoney(data.principal_minor, data.currency)} ·{' '}
              {formatMoney(data.projected_annual_interest_minor ?? 0, data.currency)} projected
              annual
            </span>
          </div>
        </>
      ) : null}

      <div className="rounded-md border border-slate-200 p-4">
        <h3 className="text-sm font-semibold">Record a valuation</h3>
        <form
          className="mt-3 space-y-3"
          onSubmit={(event) => void onCreateValuation(event)}
          noValidate
        >
          {error !== null ? <Alert variant="error">{error}</Alert> : null}
          <TextInput
            label="Value"
            inputMode="decimal"
            required
            value={value}
            {...(fieldError !== null ? { error: fieldError } : {})}
            onChange={(event) => setValue(event.target.value)}
          />
          <TextInput
            label="As of"
            type="date"
            required
            value={asOf}
            onChange={(event) => setAsOf(event.target.value)}
          />
          <TextAreaInput
            label="Notes"
            rows={2}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
          <Button type="submit" size="sm" isLoading={createValuation.isPending}>
            Add valuation
          </Button>
        </form>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold">Valuation history</h3>
        {valuations.isPending ? <LoadingState label="Loading valuations…" /> : null}
        {valuations.error !== null ? <ErrorAlert error={valuations.error} /> : null}
        {!valuations.isPending && (valuations.data?.items.length ?? 0) === 0 ? (
          <EmptyState
            title="No snapshots"
            description="Record a statement value to chart returns."
          />
        ) : null}
        {(valuations.data?.items.length ?? 0) > 0 ? (
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                <th scope="col" className="py-2">
                  Date
                </th>
                <th scope="col" className="py-2 text-right">
                  Value
                </th>
                <th scope="col" className="py-2">
                  Source
                </th>
                <th scope="col" className="py-2">
                  Notes
                </th>
                <th scope="col" className="py-2 text-right">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(valuations.data?.items ?? []).map((valuation) => (
                <tr key={valuation.id}>
                  <td className="py-2">{valuation.as_of}</td>
                  <td className="py-2 text-right">
                    {formatMoney(valuation.value_minor, investment.currency)}
                  </td>
                  <td className="py-2">{valuation.source}</td>
                  <td className="py-2">{valuation.notes ?? '—'}</td>
                  <td className="py-2 text-right">
                    <Button variant="ghost" size="sm" onClick={() => setDeleting(valuation)}>
                      Delete
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </div>

      <ConfirmDialog
        open={deleting !== null}
        title="Delete valuation?"
        message="The snapshot is removed; accrued value may be used again."
        onConfirm={() => void onDeleteValuation()}
        onCancel={() => setDeleting(null)}
        isLoading={deleteValuation.isPending}
      />
    </Modal>
  );
};
