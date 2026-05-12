import { useState, type JSX } from 'react';

import {
  useAccounts,
  useDeleteInvestment,
  useInvestmentReturns,
  useInvestments,
  useUpdateInvestment,
} from '@/api/hooks';
import type { InvestmentResponse } from '@/api/types';
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorAlert,
  LoadingState,
  PageHeader,
} from '@/components/ui';
import { InvestmentDetail } from '@/features/investments/InvestmentDetail';
import { InvestmentForm } from '@/features/investments/InvestmentForm';
import { valueSourceLabels } from '@/lib/labels';
import { formatMoney, formatPercent } from '@/lib/money';

const InvestmentRow = ({
  investment,
  onDetail,
  onEdit,
  onDelete,
  onArchive,
}: {
  investment: InvestmentResponse;
  onDetail: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onArchive: () => void;
}): JSX.Element => {
  const returns = useInvestmentReturns(investment.id);
  const data = returns.data;

  return (
    <tr>
      <td className="px-4 py-3 font-medium">{investment.name}</td>
      <td className="px-4 py-3">
        {investment.investment_type === 'fixed_rate' ? 'Fixed rate' : 'Market priced'}
        {investment.rate !== null ? (
          <span className="block text-xs text-slate-500">
            {investment.rate}% {investment.rate_period === 'annual' ? 'p.a.' : 'p.m.'}
          </span>
        ) : null}
      </td>
      <td className="px-4 py-3 text-right">
        {formatMoney(investment.principal_minor, investment.currency)}
      </td>
      <td className="px-4 py-3 text-right">
        {data === undefined ? '…' : formatMoney(data.value_minor, data.currency)}
      </td>
      <td
        className={`px-4 py-3 text-right ${
          data !== undefined && data.gain_minor < 0 ? 'text-red-700' : 'text-emerald-700'
        }`}
      >
        {data === undefined ? '…' : formatMoney(data.gain_minor, data.currency)}
        {data !== undefined ? (
          <span className="block text-xs text-slate-500">{formatPercent(data.gain_percent)}</span>
        ) : null}
      </td>
      <td className="px-4 py-3">
        {data === undefined ? (
          '—'
        ) : (
          <Badge tone="info">{valueSourceLabels[data.value_source]}</Badge>
        )}
        {investment.is_archived ? <Badge tone="neutral">Archived</Badge> : null}
      </td>
      <td className="px-4 py-3">
        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onDetail}>
            View
          </Button>
          <Button variant="ghost" size="sm" onClick={onEdit}>
            Edit
          </Button>
          <Button variant="ghost" size="sm" onClick={onArchive}>
            {investment.is_archived ? 'Restore' : 'Archive'}
          </Button>
          <Button variant="ghost" size="sm" onClick={onDelete}>
            Delete
          </Button>
        </div>
      </td>
    </tr>
  );
};

export const InvestmentsPage = (): JSX.Element => {
  const [includeArchived, setIncludeArchived] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<InvestmentResponse | null>(null);
  const [detail, setDetail] = useState<InvestmentResponse | null>(null);
  const [deleting, setDeleting] = useState<InvestmentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const investments = useInvestments(includeArchived);
  const accounts = useAccounts();
  const remove = useDeleteInvestment();
  const update = useUpdateInvestment();

  const confirmDelete = async (): Promise<void> => {
    if (deleting === null) return;
    setError(null);
    try {
      await remove.mutateAsync(deleting.id);
      setDeleting(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not delete the investment');
    }
  };

  const toggleArchive = async (investment: InvestmentResponse): Promise<void> => {
    try {
      await update.mutateAsync({
        id: investment.id,
        body: { is_archived: !investment.is_archived },
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not archive the investment');
    }
  };

  const items = investments.data?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Investments"
        description="Fixed-rate and market-priced holdings, valued in their own currency."
        actions={<Button onClick={() => setFormOpen(true)}>New investment</Button>}
      />

      {error !== null ? <ErrorAlert error={error} /> : null}
      <div className="mb-4 flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(event) => setIncludeArchived(event.target.checked)}
          />
          Show archived investments
        </label>
      </div>

      {investments.error !== null ? <ErrorAlert error={investments.error} /> : null}
      {investments.isPending ? <LoadingState label="Loading investments…" /> : null}

      {!investments.isPending && items.length === 0 ? (
        <EmptyState
          title="No investments yet"
          description="Track a fixed deposit, bond or market-priced holding."
          action={<Button onClick={() => setFormOpen(true)}>Add your first investment</Button>}
        />
      ) : null}

      {items.length > 0 ? (
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
                <th scope="col" className="px-4 py-3 text-right font-medium text-slate-600">
                  Principal
                </th>
                <th scope="col" className="px-4 py-3 text-right font-medium text-slate-600">
                  Value
                </th>
                <th scope="col" className="px-4 py-3 text-right font-medium text-slate-600">
                  Gain
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium text-slate-600">
                  Basis
                </th>
                <th scope="col" className="px-4 py-3 text-right font-medium text-slate-600">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((investment) => (
                <InvestmentRow
                  key={investment.id}
                  investment={investment}
                  onDetail={() => setDetail(investment)}
                  onEdit={() => setEditing(investment)}
                  onDelete={() => setDeleting(investment)}
                  onArchive={() => void toggleArchive(investment)}
                />
              ))}
            </tbody>
          </table>
        </Card>
      ) : null}

      {formOpen || editing !== null ? (
        <InvestmentForm
          investment={editing}
          accounts={accounts.data?.items ?? []}
          onClose={() => {
            setFormOpen(false);
            setEditing(null);
          }}
        />
      ) : null}

      {detail !== null ? (
        <InvestmentDetail
          investment={detail}
          onClose={() => setDetail(null)}
          onEdit={() => {
            setEditing(detail);
            setDetail(null);
          }}
        />
      ) : null}

      <ConfirmDialog
        open={deleting !== null}
        title="Delete investment?"
        message="Its valuation history is removed. Transactions are unaffected."
        onConfirm={() => void confirmDelete()}
        onCancel={() => setDeleting(null)}
        isLoading={remove.isPending}
      />
    </div>
  );
};
