import { useState, type SyntheticEvent, type JSX } from 'react';

import { ApiError } from '@/api/client';
import { useImportTransactions } from '@/api/hooks';
import type { AccountResponse, CategoryResponse, CsvImportResult } from '@/api/types';
import { Alert, Button, Modal, SelectInput, TextAreaInput, TextInput } from '@/components/ui';

const sampleCsv = 'date,amount,description\n2026-01-02,-24.99,Coffee\n2026-01-03,100.00,Refund';

export const ImportDialog = ({
  accounts,
  categories,
  onClose,
}: {
  accounts: AccountResponse[];
  categories: CategoryResponse[];
  onClose: () => void;
}): JSX.Element => {
  const importMutation = useImportTransactions();
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? '');
  const [csv, setCsv] = useState(sampleCsv);
  const [dateColumn, setDateColumn] = useState('date');
  const [amountColumn, setAmountColumn] = useState('amount');
  const [descriptionColumn, setDescriptionColumn] = useState('description');
  const [categoryColumn, setCategoryColumn] = useState('');
  const [typeColumn, setTypeColumn] = useState('');
  const [externalIdColumn, setExternalIdColumn] = useState('');
  const [dateFormat, setDateFormat] = useState('%Y-%m-%d');
  const [defaultCategoryId, setDefaultCategoryId] = useState('');
  const [signConvention, setSignConvention] = useState<
    'negative_is_expense' | 'positive_is_expense'
  >('negative_is_expense');
  const [dryRun, setDryRun] = useState(false);
  const [result, setResult] = useState<CsvImportResult | null>(null);
  const [error, setError] = useState<unknown>(null);

  const onSubmit = async (event: SyntheticEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setError(null);
    setResult(null);
    try {
      const response = await importMutation.mutateAsync({
        account_id: accountId,
        csv,
        mapping: {
          date: dateColumn,
          amount: amountColumn,
          ...(descriptionColumn !== '' ? { description: descriptionColumn } : {}),
          ...(categoryColumn !== '' ? { category: categoryColumn } : {}),
          ...(typeColumn !== '' ? { type: typeColumn } : {}),
          ...(externalIdColumn !== '' ? { external_id: externalIdColumn } : {}),
        },
        date_format: dateFormat,
        default_description: 'Imported transaction',
        amount_sign: signConvention,
        ...(defaultCategoryId !== '' ? { default_category_id: defaultCategoryId } : {}),
        dry_run: dryRun,
      });
      setResult(response);
    } catch (caught) {
      setError(caught);
    }
  };

  const apiError = error instanceof ApiError ? error : null;

  return (
    <Modal
      open
      title="Import transactions from CSV"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
          <Button type="submit" form="import-form" isLoading={importMutation.isPending}>
            {dryRun ? 'Validate only' : 'Import CSV'}
          </Button>
        </>
      }
    >
      <form
        id="import-form"
        className="space-y-4"
        onSubmit={(event) => void onSubmit(event)}
        noValidate
      >
        {error !== null && apiError === null ? (
          <Alert variant="error">{error instanceof Error ? error.message : 'Import failed'}</Alert>
        ) : null}
        {apiError !== null ? (
          <Alert variant="error">
            <p>{apiError.message}</p>
            {apiError.errors !== undefined && apiError.errors.length > 0 ? (
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {apiError.errors.map((rowError) => (
                  <li key={`${String(rowError.row)}-${rowError.message}`}>
                    Row {String(rowError.row)}: {rowError.message}
                  </li>
                ))}
              </ul>
            ) : null}
          </Alert>
        ) : null}
        {result !== null ? (
          <Alert variant={result.error_count > 0 ? 'warning' : 'success'}>
            {result.dry_run ? 'Validation complete: ' : 'Import complete: '}
            {result.imported_count} to import, {result.skipped_count} duplicates skipped
            {result.error_count > 0 ? `, ${String(result.error_count)} errors` : ''}.
          </Alert>
        ) : null}

        <SelectInput
          label="Destination account"
          value={accountId}
          onChange={(event) => setAccountId(event.target.value)}
        >
          <option value="">Choose an account</option>
          {accounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name} ({account.currency})
            </option>
          ))}
        </SelectInput>

        <TextAreaInput
          label="CSV contents"
          rows={8}
          required
          value={csv}
          onChange={(event) => setCsv(event.target.value)}
          hint="Paste the statement or export here. The header row must match the column names below."
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <TextInput
            label="Date column"
            required
            value={dateColumn}
            onChange={(event) => setDateColumn(event.target.value)}
          />
          <TextInput
            label="Amount column"
            required
            value={amountColumn}
            onChange={(event) => setAmountColumn(event.target.value)}
          />
          <TextInput
            label="Description column (optional)"
            value={descriptionColumn}
            onChange={(event) => setDescriptionColumn(event.target.value)}
          />
          <TextInput
            label="Category column (optional)"
            value={categoryColumn}
            onChange={(event) => setCategoryColumn(event.target.value)}
          />
          <TextInput
            label="Type column (optional)"
            value={typeColumn}
            onChange={(event) => setTypeColumn(event.target.value)}
          />
          <TextInput
            label="Bank reference column (optional)"
            value={externalIdColumn}
            onChange={(event) => setExternalIdColumn(event.target.value)}
          />
        </div>

        <TextInput
          label="Date format"
          value={dateFormat}
          onChange={(event) => setDateFormat(event.target.value)}
          hint="Python-style strftime, e.g. %Y-%m-%d or %d/%m/%Y."
        />

        <SelectInput
          label="Amount sign"
          value={signConvention}
          onChange={(event) =>
            setSignConvention(event.target.value as 'negative_is_expense' | 'positive_is_expense')
          }
        >
          <option value="negative_is_expense">Negative amounts are expenses</option>
          <option value="positive_is_expense">Positive amounts are expenses</option>
        </SelectInput>

        <SelectInput
          label="Default category (optional)"
          value={defaultCategoryId}
          onChange={(event) => setDefaultCategoryId(event.target.value)}
        >
          <option value="">None</option>
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </SelectInput>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(event) => setDryRun(event.target.checked)}
          />
          Validate and report without writing anything
        </label>
      </form>
    </Modal>
  );
};
