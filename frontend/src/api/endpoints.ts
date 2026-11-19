/** Typed endpoint functions, one place per resource. */

import { apiDownload, apiRequest, type QueryValue } from '@/api/client';
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
  RegisterRequest,
  TokenResponse,
  TransactionCreate,
  TransactionResponse,
  TransactionUpdate,
  TransferCreate,
  TransferResponse,
  UserResponse,
  ValuationCreate,
  ValuationResponse,
} from '@/api/types';

const API = '/api/v1';

// --- auth -----------------------------------------------------------------

export const loginRequest = (body: { email: string; password: string }): Promise<TokenResponse> =>
  apiRequest<TokenResponse>(`${API}/auth/login`, { method: 'POST', body, auth: false });

export const registerRequest = (body: RegisterRequest): Promise<UserResponse> =>
  apiRequest<UserResponse>(`${API}/auth/register`, { method: 'POST', body, auth: false });

export const logoutRequest = (): Promise<void> =>
  apiRequest<undefined>(`${API}/auth/logout`, { method: 'POST', auth: false });

export const meRequest = (): Promise<UserResponse> => apiRequest<UserResponse>(`${API}/auth/me`);

// --- accounts -------------------------------------------------------------

export const listAccounts = (includeArchived = false): Promise<Page<AccountResponse>> =>
  apiRequest<Page<AccountResponse>>(`${API}/accounts`, {
    query: { limit: 100, include_archived: includeArchived },
  });

export const createAccount = (body: AccountCreate): Promise<AccountResponse> =>
  apiRequest<AccountResponse>(`${API}/accounts`, { method: 'POST', body });

export const updateAccount = (id: string, body: AccountUpdate): Promise<AccountResponse> =>
  apiRequest<AccountResponse>(`${API}/accounts/${id}`, { method: 'PATCH', body });

export const deleteAccount = (id: string): Promise<void> =>
  apiRequest<undefined>(`${API}/accounts/${id}`, { method: 'DELETE' });

export const accountBalance = (id: string): Promise<AccountBalanceResponse> =>
  apiRequest<AccountBalanceResponse>(`${API}/accounts/${id}/balance`);

// --- categories -----------------------------------------------------------

export const listCategories = (includeArchived = false): Promise<Page<CategoryResponse>> =>
  apiRequest<Page<CategoryResponse>>(`${API}/categories`, {
    query: { limit: 200, include_archived: includeArchived },
  });

export const createCategory = (body: CategoryCreate): Promise<CategoryResponse> =>
  apiRequest<CategoryResponse>(`${API}/categories`, { method: 'POST', body });

export const updateCategory = (id: string, body: CategoryUpdate): Promise<CategoryResponse> =>
  apiRequest<CategoryResponse>(`${API}/categories/${id}`, { method: 'PATCH', body });

export const deleteCategory = (id: string): Promise<void> =>
  apiRequest<undefined>(`${API}/categories/${id}`, { method: 'DELETE' });

// --- transactions ---------------------------------------------------------

export interface TransactionFilters extends QueryValue {
  limit?: number;
  offset?: number;
  account_id?: string;
  category_id?: string;
  transaction_type?: string;
  date_from?: string;
  date_to?: string;
}

export const listTransactions = (
  filters: TransactionFilters = {},
): Promise<Page<TransactionResponse>> =>
  apiRequest<Page<TransactionResponse>>(`${API}/transactions`, {
    query: { limit: 50, offset: 0, ...filters },
  });

export const createTransaction = (body: TransactionCreate): Promise<TransactionResponse> =>
  apiRequest<TransactionResponse>(`${API}/transactions`, { method: 'POST', body });

export const updateTransaction = (
  id: string,
  body: TransactionUpdate,
): Promise<TransactionResponse> =>
  apiRequest<TransactionResponse>(`${API}/transactions/${id}`, { method: 'PATCH', body });

export const deleteTransaction = (id: string): Promise<void> =>
  apiRequest<undefined>(`${API}/transactions/${id}`, { method: 'DELETE' });

export const createTransfer = (body: TransferCreate): Promise<TransferResponse> =>
  apiRequest<TransferResponse>(`${API}/transactions/transfers`, { method: 'POST', body });

export const importTransactions = (body: CsvImportRequest): Promise<CsvImportResult> =>
  apiRequest<CsvImportResult>(`${API}/transactions/import`, { method: 'POST', body });

// --- budgets --------------------------------------------------------------

export const listBudgets = (includeArchived = false): Promise<Page<BudgetResponse>> =>
  apiRequest<Page<BudgetResponse>>(`${API}/budgets`, {
    query: { limit: 200, include_archived: includeArchived },
  });

export const createBudget = (body: BudgetCreate): Promise<BudgetResponse> =>
  apiRequest<BudgetResponse>(`${API}/budgets`, { method: 'POST', body });

export const updateBudget = (id: string, body: BudgetUpdate): Promise<BudgetResponse> =>
  apiRequest<BudgetResponse>(`${API}/budgets/${id}`, { method: 'PATCH', body });

export const deleteBudget = (id: string): Promise<void> =>
  apiRequest<undefined>(`${API}/budgets/${id}`, { method: 'DELETE' });

export const budgetStatus = (period: string): Promise<BudgetPortfolioStatus> =>
  apiRequest<BudgetPortfolioStatus>(`${API}/budgets/status`, { query: { period } });

// --- investments ----------------------------------------------------------

export const listInvestments = (includeArchived = false): Promise<Page<InvestmentResponse>> =>
  apiRequest<Page<InvestmentResponse>>(`${API}/investments`, {
    query: { limit: 200, include_archived: includeArchived },
  });

export const createInvestment = (body: InvestmentCreate): Promise<InvestmentResponse> =>
  apiRequest<InvestmentResponse>(`${API}/investments`, { method: 'POST', body });

export const updateInvestment = (id: string, body: InvestmentUpdate): Promise<InvestmentResponse> =>
  apiRequest<InvestmentResponse>(`${API}/investments/${id}`, { method: 'PATCH', body });

export const deleteInvestment = (id: string): Promise<void> =>
  apiRequest<undefined>(`${API}/investments/${id}`, { method: 'DELETE' });

export const investmentReturns = (id: string, asOf?: string): Promise<InvestmentReturnsResponse> =>
  apiRequest<InvestmentReturnsResponse>(`${API}/investments/${id}/returns`, {
    query: asOf !== undefined ? { as_of: asOf } : {},
  });

export const listValuations = (id: string): Promise<Page<ValuationResponse>> =>
  apiRequest<Page<ValuationResponse>>(`${API}/investments/${id}/valuations`, {
    query: { limit: 200 },
  });

export const createValuation = (id: string, body: ValuationCreate): Promise<ValuationResponse> =>
  apiRequest<ValuationResponse>(`${API}/investments/${id}/valuations`, { method: 'POST', body });

export const deleteValuation = (id: string, valuationId: string): Promise<void> =>
  apiRequest<undefined>(`${API}/investments/${id}/valuations/${valuationId}`, { method: 'DELETE' });

// --- exchange rates -------------------------------------------------------

export const listExchangeRates = (): Promise<Page<ExchangeRateResponse>> =>
  apiRequest<Page<ExchangeRateResponse>>(`${API}/exchange-rates`, { query: { limit: 100 } });

export const createExchangeRate = (body: ExchangeRateCreate): Promise<ExchangeRateResponse> =>
  apiRequest<ExchangeRateResponse>(`${API}/exchange-rates`, { method: 'POST', body });

// --- reports --------------------------------------------------------------

export const netWorth = (asOf?: string): Promise<NetWorthResponse> =>
  apiRequest<NetWorthResponse>(`${API}/reports/net-worth`, {
    query: asOf !== undefined ? { as_of: asOf } : {},
  });

export const netWorthHistory = (months: number, asOf?: string): Promise<NetWorthHistoryResponse> =>
  apiRequest<NetWorthHistoryResponse>(`${API}/reports/net-worth/history`, {
    query: { months, ...(asOf ? { as_of: asOf } : {}) },
  });

export const cashFlow = (dateFrom?: string, dateTo?: string): Promise<CashFlowResponse> =>
  apiRequest<CashFlowResponse>(`${API}/reports/cash-flow`, {
    query: {
      ...(dateFrom ? { date_from: dateFrom } : {}),
      ...(dateTo ? { date_to: dateTo } : {}),
    },
  });

export const categoryBreakdown = (params: {
  kind: 'expense' | 'income';
  dateFrom?: string;
  dateTo?: string;
  includeSubcategories?: boolean;
}): Promise<CategoryBreakdownResponse> =>
  apiRequest<CategoryBreakdownResponse>(`${API}/reports/category-breakdown`, {
    query: {
      kind: params.kind,
      include_subcategories: params.includeSubcategories ?? true,
      ...(params.dateFrom ? { date_from: params.dateFrom } : {}),
      ...(params.dateTo ? { date_to: params.dateTo } : {}),
    },
  });

export const downloadTransactionsCsv = (
  dateFrom?: string,
  dateTo?: string,
): ReturnType<typeof apiDownload> =>
  apiDownload(`${API}/reports/transactions.csv`, {
    fallbackFilename: 'transactions.csv',
    query: {
      ...(dateFrom ? { date_from: dateFrom } : {}),
      ...(dateTo ? { date_to: dateTo } : {}),
    },
  });

// --- recurring ------------------------------------------------------------

export const listRecurringRules = (includeInactive = true): Promise<Page<RecurringRuleResponse>> =>
  apiRequest<Page<RecurringRuleResponse>>(`${API}/recurring-rules`, {
    query: { limit: 200, include_inactive: includeInactive },
  });

export const createRecurringRule = (body: RecurringRuleCreate): Promise<RecurringRuleResponse> =>
  apiRequest<RecurringRuleResponse>(`${API}/recurring-rules`, { method: 'POST', body });

export const updateRecurringRule = (
  id: string,
  body: RecurringRuleUpdate,
): Promise<RecurringRuleResponse> =>
  apiRequest<RecurringRuleResponse>(`${API}/recurring-rules/${id}`, { method: 'PATCH', body });

export const deleteRecurringRule = (id: string): Promise<void> =>
  apiRequest<undefined>(`${API}/recurring-rules/${id}`, { method: 'DELETE' });

export const runRecurringRule = (id: string, asOf?: string): Promise<RecurringRunResponse> =>
  apiRequest<RecurringRunResponse>(`${API}/recurring-rules/${id}/run`, {
    method: 'POST',
    query: asOf !== undefined ? { as_of: asOf } : {},
  });

// --- export ---------------------------------------------------------------

export const downloadFullExport = (): ReturnType<typeof apiDownload> =>
  apiDownload(`${API}/export`, { fallbackFilename: 'budgetting-export.json' });
