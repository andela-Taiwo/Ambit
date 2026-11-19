import { useState, type SyntheticEvent, type JSX } from 'react';

import { downloadBlob } from '@/api/client';
import { useCreateExchangeRate, useDownloadFullExport, useExchangeRates } from '@/api/hooks';
import { useHealth } from '@/api/queries';
import { useAuthStore } from '@/features/auth/store';
import {
  Alert,
  Button,
  Card,
  EmptyState,
  ErrorAlert,
  LoadingState,
  PageHeader,
  SelectInput,
  TextInput,
} from '@/components/ui';
import { formatDateTime, todayIso } from '@/lib/dates';
import { SUPPORTED_CURRENCIES } from '@/lib/money';

const BackendStatus = (): JSX.Element => {
  const health = useHealth();
  const label = health.isPending
    ? 'Checking backend…'
    : health.isError
      ? 'Backend unavailable'
      : 'Backend connected';
  return (
    <p role="status" className="text-sm text-slate-600">
      {label}
    </p>
  );
};

export const SettingsPage = (): JSX.Element => {
  const user = useAuthStore((state) => state.user);
  const rates = useExchangeRates();
  const createRate = useCreateExchangeRate();
  const exportMutation = useDownloadFullExport();
  const [base, setBase] = useState(user?.base_currency ?? 'GBP');
  const [quote, setQuote] = useState('USD');
  const [rate, setRate] = useState('');
  const [asOf, setAsOf] = useState(`${todayIso()}T00:00`);
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [exportMessage, setExportMessage] = useState<string | null>(null);

  const onSubmit = async (event: SyntheticEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setError(null);
    const numeric = Number.parseFloat(rate);
    if (!Number.isFinite(numeric) || numeric <= 0) {
      setFieldError('Enter a positive rate');
      return;
    }
    if (base === quote) {
      setFieldError('Choose two different currencies');
      return;
    }
    setFieldError(null);
    try {
      await createRate.mutateAsync({
        base_currency: base,
        quote_currency: quote,
        rate,
        as_of: new Date(asOf).toISOString(),
      });
      setRate('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not save the rate');
    }
  };

  const onExport = async (): Promise<void> => {
    setExportMessage(null);
    try {
      const file = await exportMutation.mutateAsync();
      downloadBlob(file.blob, file.filename);
      setExportMessage(`Downloaded ${file.filename}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not export your data');
    }
  };

  return (
    <div>
      <PageHeader
        title="Settings & export"
        description="Your base currency, manual exchange rates and a full data export."
        actions={
          <Button
            variant="secondary"
            onClick={() => void onExport()}
            isLoading={exportMutation.isPending}
          >
            Export all data (JSON)
          </Button>
        }
      />

      {exportMessage !== null ? <Alert variant="success">{exportMessage}</Alert> : null}
      {error !== null ? <ErrorAlert error={error} /> : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="text-lg font-semibold">Profile</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-slate-600">Name</dt>
              <dd className="font-medium">{user?.display_name ?? '—'}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-600">Email</dt>
              <dd className="font-medium">{user?.email ?? '—'}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-600">Base currency</dt>
              <dd className="font-medium">{user?.base_currency ?? '—'}</dd>
            </div>
          </dl>
          <p className="mt-4 text-xs text-slate-500">
            Reports and net worth are expressed in the base currency. Manual rates are private to
            your account.
          </p>
          <div className="mt-4 border-t border-slate-100 pt-3">
            <BackendStatus />
          </div>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold">Record a manual exchange rate</h2>
          <form className="mt-3 space-y-3" onSubmit={(event) => void onSubmit(event)} noValidate>
            <SelectInput
              label="Base currency"
              value={base}
              onChange={(event) => setBase(event.target.value)}
            >
              {SUPPORTED_CURRENCIES.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </SelectInput>
            <SelectInput
              label="Quote currency"
              value={quote}
              onChange={(event) => setQuote(event.target.value)}
            >
              {SUPPORTED_CURRENCIES.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </SelectInput>
            <TextInput
              label="Rate"
              inputMode="decimal"
              required
              hint="One unit of the base currency buys this many quote units."
              value={rate}
              {...(fieldError !== null ? { error: fieldError } : {})}
              onChange={(event) => setRate(event.target.value)}
            />
            <TextInput
              label="As of"
              type="datetime-local"
              required
              value={asOf}
              onChange={(event) => setAsOf(event.target.value)}
            />
            <Button type="submit" isLoading={createRate.isPending}>
              Save rate
            </Button>
          </form>
        </Card>
      </div>

      <Card className="mt-6">
        <h2 className="text-lg font-semibold">Exchange rates</h2>
        {rates.error !== null ? <ErrorAlert error={rates.error} /> : null}
        {rates.isPending ? <LoadingState label="Loading rates…" /> : null}
        {!rates.isPending && (rates.data?.items.length ?? 0) === 0 ? (
          <EmptyState
            title="No rates recorded"
            description="Add a manual rate to convert foreign amounts."
          />
        ) : null}
        {(rates.data?.items.length ?? 0) > 0 ? (
          <table className="mt-3 min-w-full divide-y divide-slate-200 text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-slate-500">
                <th scope="col" className="py-2">
                  Pair
                </th>
                <th scope="col" className="py-2 text-right">
                  Rate
                </th>
                <th scope="col" className="py-2">
                  As of
                </th>
                <th scope="col" className="py-2">
                  Source
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(rates.data?.items ?? []).map((item) => (
                <tr key={item.id}>
                  <td className="py-2 font-medium">
                    {item.base_currency} → {item.quote_currency}
                  </td>
                  <td className="py-2 text-right">{item.rate}</td>
                  <td className="py-2">{formatDateTime(item.as_of)}</td>
                  <td className="py-2">{item.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </Card>
    </div>
  );
};
