import { useState, type JSX } from 'react';

import { downloadBlob } from '@/api/client';
import {
  useCashFlow,
  useCategoryBreakdown,
  useDownloadTransactionsCsv,
  useNetWorth,
  useNetWorthHistory,
} from '@/api/hooks';
import { BarChart, LineChart } from '@/components/charts';
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorAlert,
  LoadingState,
  PageHeader,
  ProgressBar,
  SelectInput,
  StatCard,
} from '@/components/ui';
import {
  addMonthsToMonth,
  currentMonth,
  formatDate,
  monthLabel,
  monthStartIso,
  todayIso,
} from '@/lib/dates';
import { formatMoney, formatPercent } from '@/lib/money';

export const ReportsPage = (): JSX.Element => {
  const [dateFrom, setDateFrom] = useState(monthStartIso(addMonthsToMonth(currentMonth(), -5)));
  const [dateTo, setDateTo] = useState(todayIso());
  const [kind, setKind] = useState<'expense' | 'income'>('expense');
  const [downloadMessage, setDownloadMessage] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<unknown>(null);

  const netWorth = useNetWorth();
  const history = useNetWorthHistory(12);
  const cashFlow = useCashFlow(dateFrom, dateTo);
  const breakdown = useCategoryBreakdown({ kind, dateFrom, dateTo });
  const download = useDownloadTransactionsCsv();

  const baseCurrency = netWorth.data?.base_currency ?? 'GBP';

  const onDownload = async (): Promise<void> => {
    setDownloadError(null);
    setDownloadMessage(null);
    try {
      const file = await download.mutateAsync({ dateFrom, dateTo });
      downloadBlob(file.blob, file.filename);
      setDownloadMessage(`Downloaded ${file.filename}`);
    } catch (caught) {
      setDownloadError(caught);
    }
  };

  const cashItems = cashFlow.data?.items ?? [];
  const breakdownItems = breakdown.data?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Reports"
        description="Net worth, cash flow and category spending, converted to your base currency."
        actions={
          <Button
            variant="secondary"
            onClick={() => void onDownload()}
            isLoading={download.isPending}
          >
            Download transactions CSV
          </Button>
        }
      />

      {downloadMessage !== null ? <Alert variant="success">{downloadMessage}</Alert> : null}
      {downloadError !== null ? <ErrorAlert error={downloadError} /> : null}

      {netWorth.error !== null ? <ErrorAlert error={netWorth.error} /> : null}
      {netWorth.isPending ? (
        <LoadingState label="Calculating net worth…" />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard
              label="Net worth"
              value={formatMoney(netWorth.data?.total_minor ?? 0, baseCurrency)}
            />
            <StatCard
              label="Cash"
              value={formatMoney(netWorth.data?.accounts_total_minor ?? 0, baseCurrency)}
            />
            <StatCard
              label="Investments"
              value={formatMoney(netWorth.data?.investments_total_minor ?? 0, baseCurrency)}
            />
          </div>

          <Card className="mt-6">
            <h2 className="text-lg font-semibold">Net worth over time</h2>
            {history.error !== null ? <ErrorAlert error={history.error} /> : null}
            {history.isPending ? (
              <LoadingState label="Loading history…" />
            ) : (
              <LineChart
                label="Net worth history"
                points={(history.data?.points ?? []).map((point) => ({
                  label: formatDate(point.as_of),
                  value: point.total_minor,
                }))}
                formatValue={(value) => formatMoney(value, baseCurrency)}
              />
            )}
          </Card>

          <Card className="mt-6">
            <h2 className="text-lg font-semibold">Accounts and holdings</h2>
            <table className="mt-3 min-w-full divide-y divide-slate-200 text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-slate-500">
                  <th scope="col" className="py-2">
                    Name
                  </th>
                  <th scope="col" className="py-2">
                    Currency
                  </th>
                  <th scope="col" className="py-2 text-right">
                    Value
                  </th>
                  <th scope="col" className="py-2 text-right">
                    Base
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(netWorth.data?.accounts ?? []).map((component) => (
                  <tr key={component.account_id}>
                    <td className="py-2">{component.name}</td>
                    <td className="py-2">{component.balance.currency}</td>
                    <td className="py-2 text-right">
                      {formatMoney(component.balance.amount_minor, component.balance.currency)}
                    </td>
                    <td className="py-2 text-right">
                      {formatMoney(component.balance.base_minor, baseCurrency)}
                    </td>
                  </tr>
                ))}
                {(netWorth.data?.investments ?? []).map((component) => (
                  <tr key={component.investment_id}>
                    <td className="py-2">{component.name}</td>
                    <td className="py-2">{component.value.currency}</td>
                    <td className="py-2 text-right">
                      {formatMoney(component.value.amount_minor, component.value.currency)}
                    </td>
                    <td className="py-2 text-right">
                      {formatMoney(component.value.base_minor, baseCurrency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}

      <Card className="mt-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 className="text-lg font-semibold">Cash flow</h2>
          <div className="flex flex-wrap gap-3">
            <label className="text-sm">
              <span className="block font-medium text-slate-700">From</span>
              <input
                type="date"
                value={dateFrom}
                onChange={(event) => setDateFrom(event.target.value)}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </label>
            <label className="text-sm">
              <span className="block font-medium text-slate-700">To</span>
              <input
                type="date"
                value={dateTo}
                onChange={(event) => setDateTo(event.target.value)}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
            </label>
          </div>
        </div>
        {cashFlow.error !== null ? <ErrorAlert error={cashFlow.error} /> : null}
        {cashFlow.isPending ? <LoadingState label="Loading cash flow…" /> : null}
        {!cashFlow.isPending && cashItems.length === 0 ? (
          <EmptyState title="No cash flow in this range" />
        ) : null}
        {cashItems.length > 0 ? (
          <>
            <BarChart
              label="Monthly net cash flow"
              points={cashItems.map((item) => ({
                label: monthLabel(item.period_start.slice(0, 7)),
                value: item.net_minor,
              }))}
              formatValue={(value) => formatMoney(value, baseCurrency)}
            />
            <table className="mt-4 min-w-full divide-y divide-slate-200 text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-slate-500">
                  <th scope="col" className="py-2">
                    Month
                  </th>
                  <th scope="col" className="py-2 text-right">
                    Income
                  </th>
                  <th scope="col" className="py-2 text-right">
                    Expense
                  </th>
                  <th scope="col" className="py-2 text-right">
                    Net
                  </th>
                  <th scope="col" className="py-2 text-right">
                    Transactions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {cashItems.map((item) => (
                  <tr key={item.period_start}>
                    <td className="py-2">{monthLabel(item.period_start.slice(0, 7))}</td>
                    <td className="py-2 text-right">
                      {formatMoney(item.income_minor, baseCurrency)}
                    </td>
                    <td className="py-2 text-right">
                      {formatMoney(item.expense_minor, baseCurrency)}
                    </td>
                    <td
                      className={`py-2 text-right ${item.net_minor < 0 ? 'text-red-700' : 'text-emerald-700'}`}
                    >
                      {formatMoney(item.net_minor, baseCurrency)}
                    </td>
                    <td className="py-2 text-right">{item.transaction_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : null}
      </Card>

      <Card className="mt-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 className="text-lg font-semibold">Category breakdown</h2>
          <SelectInput
            label="Kind"
            value={kind}
            onChange={(event) => setKind(event.target.value as 'expense' | 'income')}
          >
            <option value="expense">Expenses</option>
            <option value="income">Income</option>
          </SelectInput>
        </div>
        {breakdown.error !== null ? <ErrorAlert error={breakdown.error} /> : null}
        {breakdown.isPending ? <LoadingState label="Loading categories…" /> : null}
        {!breakdown.isPending && breakdownItems.length === 0 ? (
          <EmptyState title="No transactions in this range" />
        ) : null}
        <ul className="mt-3 space-y-3">
          {breakdownItems.map((item) => (
            <li key={`${item.category_id ?? 'uncategorized'}-${item.name}`}>
              <div className="mb-1 flex items-center justify-between gap-2 text-sm">
                <span className="font-medium">{item.name}</span>
                <span>
                  {formatMoney(item.total_minor, baseCurrency)}{' '}
                  <span className="text-xs text-slate-500">
                    ({formatPercent(item.percent_of_total)} · {item.transaction_count} tx)
                  </span>
                </span>
              </div>
              <ProgressBar
                value={Number.parseFloat(item.percent_of_total)}
                tone="success"
                label={`${item.name} share`}
              />
            </li>
          ))}
        </ul>
        <div className="mt-4">
          <Badge tone="neutral">
            Total {formatMoney(breakdown.data?.total_minor ?? 0, baseCurrency)}
          </Badge>
        </div>
      </Card>
    </div>
  );
};
