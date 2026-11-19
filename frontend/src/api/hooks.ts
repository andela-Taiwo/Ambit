/** TanStack Query hooks. Server state lives here; UI state stays in components. */

import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';

import {
  accountBalance,
  budgetStatus,
  cashFlow,
  categoryBreakdown,
  createAccount,
  createBudget,
  createCategory,
  createExchangeRate,
  createInvestment,
  createRecurringRule,
  createTransaction,
  createTransfer,
  createValuation,
  deleteAccount,
  deleteBudget,
  deleteCategory,
  deleteInvestment,
  deleteRecurringRule,
  deleteTransaction,
  deleteValuation,
  downloadFullExport,
  downloadTransactionsCsv,
  importTransactions,
  investmentReturns,
  listAccounts,
  listBudgets,
  listCategories,
  listExchangeRates,
  listInvestments,
  listRecurringRules,
  listTransactions,
  listValuations,
  netWorth,
  netWorthHistory,
  runRecurringRule,
  updateAccount,
  updateBudget,
  updateCategory,
  updateInvestment,
  updateRecurringRule,
  updateTransaction,
  type TransactionFilters,
} from '@/api/endpoints';
import type {
  AccountBalanceResponse,
  AccountCreate,
  AccountResponse,
  AccountUpdate,
  BudgetCreate,
  BudgetPortfolioStatus,
  BudgetResponse,
  BudgetUpdate,
  CashFlowResponse,
  CategoryBreakdownResponse,
  CategoryCreate,
  CategoryResponse,
  CategoryUpdate,
  CsvImportRequest,
  CsvImportResult,
  ExchangeRateCreate,
  ExchangeRateResponse,
  InvestmentCreate,
  InvestmentResponse,
  InvestmentReturnsResponse,
  InvestmentUpdate,
  NetWorthHistoryResponse,
  NetWorthResponse,
  Page,
  RecurringRuleCreate,
  RecurringRuleResponse,
  RecurringRuleUpdate,
  RecurringRunResponse,
  TransactionCreate,
  TransactionResponse,
  TransactionUpdate,
  TransferCreate,
  TransferResponse,
  ValuationCreate,
  ValuationResponse,
} from '@/api/types';

export const queryKeys = {
  accounts: (includeArchived = false) => ['accounts', includeArchived] as const,
  accountBalance: (id: string) => ['accounts', id, 'balance'] as const,
  categories: (includeArchived = false) => ['categories', includeArchived] as const,
  transactions: (filters: TransactionFilters) => ['transactions', filters] as const,
  budgets: (includeArchived = false) => ['budgets', includeArchived] as const,
  budgetStatus: (period: string) => ['budgets', 'status', period] as const,
  investments: (includeArchived = false) => ['investments', includeArchived] as const,
  investmentReturns: (id: string, asOf?: string) =>
    ['investments', id, 'returns', asOf ?? 'today'] as const,
  valuations: (id: string) => ['investments', id, 'valuations'] as const,
  exchangeRates: () => ['exchange-rates'] as const,
  netWorth: (asOf?: string) => ['reports', 'net-worth', asOf ?? 'today'] as const,
  netWorthHistory: (months: number, asOf?: string) =>
    ['reports', 'net-worth-history', months, asOf ?? 'today'] as const,
  cashFlow: (dateFrom?: string, dateTo?: string) =>
    ['reports', 'cash-flow', dateFrom ?? '', dateTo ?? ''] as const,
  categoryBreakdown: (kind: string, dateFrom?: string, dateTo?: string) =>
    ['reports', 'category-breakdown', kind, dateFrom ?? '', dateTo ?? ''] as const,
  recurringRules: () => ['recurring-rules'] as const,
};

const useInvalidate = (): ((keys: readonly unknown[][]) => void) => {
  const queryClient = useQueryClient();
  return (keys) => {
    for (const queryKey of keys) {
      void queryClient.invalidateQueries({ queryKey });
    }
  };
};

// --- reads ----------------------------------------------------------------

export const useAccounts = (includeArchived = false): UseQueryResult<Page<AccountResponse>> =>
  useQuery({
    queryKey: queryKeys.accounts(includeArchived),
    queryFn: () => listAccounts(includeArchived),
  });

export const useAccountBalances = (
  ids: readonly string[],
): Record<string, AccountBalanceResponse | undefined> => {
  const results = useQueries({
    queries: ids.map((id) => ({
      queryKey: queryKeys.accountBalance(id),
      queryFn: () => accountBalance(id),
      enabled: id !== '',
    })),
  });
  return Object.fromEntries(ids.map((id, index) => [id, results[index]?.data]));
};

export const useCategories = (includeArchived = false): UseQueryResult<Page<CategoryResponse>> =>
  useQuery({
    queryKey: queryKeys.categories(includeArchived),
    queryFn: () => listCategories(includeArchived),
  });

export const useTransactions = (
  filters: TransactionFilters,
): UseQueryResult<Page<TransactionResponse>> =>
  useQuery({
    queryKey: queryKeys.transactions(filters),
    queryFn: () => listTransactions(filters),
    placeholderData: (previous) => previous,
  });

export const useBudgets = (includeArchived = false): UseQueryResult<Page<BudgetResponse>> =>
  useQuery({
    queryKey: queryKeys.budgets(includeArchived),
    queryFn: () => listBudgets(includeArchived),
  });

export const useBudgetStatus = (period: string): UseQueryResult<BudgetPortfolioStatus> =>
  useQuery({
    queryKey: queryKeys.budgetStatus(period),
    queryFn: () => budgetStatus(period),
  });
export const useInvestments = (includeArchived = false): UseQueryResult<Page<InvestmentResponse>> =>
  useQuery({
    queryKey: queryKeys.investments(includeArchived),
    queryFn: () => listInvestments(includeArchived),
  });

export const useInvestmentReturns = (
  id: string,
  asOf?: string,
): UseQueryResult<InvestmentReturnsResponse> =>
  useQuery({
    queryKey: queryKeys.investmentReturns(id, asOf),
    queryFn: () => investmentReturns(id, asOf),
    enabled: id !== '',
  });

export const useValuations = (id: string): UseQueryResult<Page<ValuationResponse>> =>
  useQuery({
    queryKey: queryKeys.valuations(id),
    queryFn: () => listValuations(id),
    enabled: id !== '',
  });

export const useExchangeRates = (): UseQueryResult<Page<ExchangeRateResponse>> =>
  useQuery({ queryKey: queryKeys.exchangeRates(), queryFn: listExchangeRates });
export const useNetWorth = (asOf?: string): UseQueryResult<NetWorthResponse> =>
  useQuery({ queryKey: queryKeys.netWorth(asOf), queryFn: () => netWorth(asOf) });

export const useNetWorthHistory = (
  months: number,
  asOf?: string,
): UseQueryResult<NetWorthHistoryResponse> =>
  useQuery({
    queryKey: queryKeys.netWorthHistory(months, asOf),
    queryFn: () => netWorthHistory(months, asOf),
  });

export const useCashFlow = (dateFrom?: string, dateTo?: string): UseQueryResult<CashFlowResponse> =>
  useQuery({
    queryKey: queryKeys.cashFlow(dateFrom, dateTo),
    queryFn: () => cashFlow(dateFrom, dateTo),
  });

export const useCategoryBreakdown = (params: {
  kind: 'expense' | 'income';
  dateFrom?: string;
  dateTo?: string;
  includeSubcategories?: boolean;
}): UseQueryResult<CategoryBreakdownResponse> =>
  useQuery({
    queryKey: queryKeys.categoryBreakdown(params.kind, params.dateFrom, params.dateTo),
    queryFn: () => categoryBreakdown(params),
  });

export const useRecurringRules = (
  includeInactive = true,
): UseQueryResult<Page<RecurringRuleResponse>> =>
  useQuery({
    queryKey: queryKeys.recurringRules(),
    queryFn: () => listRecurringRules(includeInactive),
  });

// --- mutations ------------------------------------------------------------

const invalidateAccounts = [
  ['accounts'],
  ['transactions'],
  ['reports', 'net-worth'],
  ['reports', 'net-worth-history'],
];

export const useCreateAccount = (): UseMutationResult<AccountResponse, Error, AccountCreate> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: createAccount,
    onSuccess: () => invalidate(invalidateAccounts),
  });
};

export const useUpdateAccount = (): UseMutationResult<
  AccountResponse,
  Error,
  { id: string; body: AccountUpdate }
> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }) => updateAccount(id, body),
    onSuccess: () => invalidate(invalidateAccounts),
  });
};

export const useDeleteAccount = (): UseMutationResult<void, Error, string> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: deleteAccount,
    onSuccess: () => invalidate(invalidateAccounts),
  });
};

export const useCreateCategory = (): UseMutationResult<CategoryResponse, Error, CategoryCreate> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: createCategory,
    onSuccess: () => invalidate([['categories'], ['transactions'], ['budgets']]),
  });
};

export const useUpdateCategory = (): UseMutationResult<
  CategoryResponse,
  Error,
  { id: string; body: CategoryUpdate }
> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }) => updateCategory(id, body),
    onSuccess: () => invalidate([['categories'], ['transactions'], ['budgets']]),
  });
};

export const useDeleteCategory = (): UseMutationResult<void, Error, string> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: deleteCategory,
    onSuccess: () => invalidate([['categories'], ['transactions'], ['budgets']]),
  });
};

const invalidateTransactions = [['transactions'], ['accounts'], ['budgets'], ['reports']];

export const useCreateTransaction = (): UseMutationResult<
  TransactionResponse,
  Error,
  TransactionCreate
> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: createTransaction,
    onSuccess: () => invalidate(invalidateTransactions),
  });
};

export const useUpdateTransaction = (): UseMutationResult<
  TransactionResponse,
  Error,
  { id: string; body: TransactionUpdate }
> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }) => updateTransaction(id, body),
    onSuccess: () => invalidate(invalidateTransactions),
  });
};

export const useDeleteTransaction = (): UseMutationResult<void, Error, string> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: deleteTransaction,
    onSuccess: () => invalidate(invalidateTransactions),
  });
};

export const useCreateTransfer = (): UseMutationResult<TransferResponse, Error, TransferCreate> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: createTransfer,
    onSuccess: () => invalidate(invalidateTransactions),
  });
};

export const useImportTransactions = (): UseMutationResult<
  CsvImportResult,
  Error,
  CsvImportRequest
> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: importTransactions,
    onSuccess: () => invalidate(invalidateTransactions),
  });
};

const invalidateBudgets = [['budgets'], ['transactions'], ['reports']];

export const useCreateBudget = (): UseMutationResult<BudgetResponse, Error, BudgetCreate> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: createBudget,
    onSuccess: () => invalidate(invalidateBudgets),
  });
};

export const useUpdateBudget = (): UseMutationResult<
  BudgetResponse,
  Error,
  { id: string; body: BudgetUpdate }
> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }) => updateBudget(id, body),
    onSuccess: () => invalidate(invalidateBudgets),
  });
};

export const useDeleteBudget = (): UseMutationResult<void, Error, string> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: deleteBudget,
    onSuccess: () => invalidate(invalidateBudgets),
  });
};

const invalidateInvestments = [
  ['investments'],
  ['reports', 'net-worth'],
  ['reports', 'net-worth-history'],
];

export const useCreateInvestment = (): UseMutationResult<
  InvestmentResponse,
  Error,
  InvestmentCreate
> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: createInvestment,
    onSuccess: () => invalidate(invalidateInvestments),
  });
};

export const useUpdateInvestment = (): UseMutationResult<
  InvestmentResponse,
  Error,
  { id: string; body: InvestmentUpdate }
> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }) => updateInvestment(id, body),
    onSuccess: () => invalidate(invalidateInvestments),
  });
};

export const useDeleteInvestment = (): UseMutationResult<void, Error, string> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: deleteInvestment,
    onSuccess: () => invalidate(invalidateInvestments),
  });
};

export const useCreateValuation = (): UseMutationResult<
  ValuationResponse,
  Error,
  { id: string; body: ValuationCreate }
> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }) => createValuation(id, body),
    onSuccess: () => invalidate([...invalidateInvestments, ['investments']]),
  });
};

export const useDeleteValuation = (): UseMutationResult<
  void,
  Error,
  { id: string; valuationId: string }
> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, valuationId }) => deleteValuation(id, valuationId),
    onSuccess: () => invalidate(invalidateInvestments),
  });
};

export const useCreateExchangeRate = (): UseMutationResult<
  ExchangeRateResponse,
  Error,
  ExchangeRateCreate
> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: createExchangeRate,
    onSuccess: () => invalidate([['exchange-rates'], ['budgets'], ['reports']]),
  });
};

const invalidateRecurring = [['recurring-rules'], ['transactions'], ['accounts']];

export const useCreateRecurringRule = (): UseMutationResult<
  RecurringRuleResponse,
  Error,
  RecurringRuleCreate
> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: createRecurringRule,
    onSuccess: () => invalidate(invalidateRecurring),
  });
};

export const useUpdateRecurringRule = (): UseMutationResult<
  RecurringRuleResponse,
  Error,
  { id: string; body: RecurringRuleUpdate }
> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }) => updateRecurringRule(id, body),
    onSuccess: () => invalidate(invalidateRecurring),
  });
};

export const useDeleteRecurringRule = (): UseMutationResult<void, Error, string> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: deleteRecurringRule,
    onSuccess: () => invalidate(invalidateRecurring),
  });
};

export const useRunRecurringRule = (): UseMutationResult<
  RecurringRunResponse,
  Error,
  { id: string; asOf?: string }
> => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, asOf }) => runRecurringRule(id, asOf),
    onSuccess: () => invalidate(invalidateRecurring),
  });
};

export const useDownloadTransactionsCsv = (): UseMutationResult<
  { blob: Blob; filename: string },
  Error,
  { dateFrom?: string; dateTo?: string }
> =>
  useMutation({
    mutationFn: ({ dateFrom, dateTo }) => downloadTransactionsCsv(dateFrom, dateTo),
  });

export const useDownloadFullExport = (): UseMutationResult<
  { blob: Blob; filename: string },
  Error,
  void
> => useMutation({ mutationFn: downloadFullExport });
