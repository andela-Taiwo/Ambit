import type { components } from '@/api/generated/schema';

export type Schemas = components['schemas'];

export type UserResponse = Schemas['UserResponse'];
export type RegisterRequest = Schemas['RegisterRequest'];
export type LoginRequest = Schemas['LoginRequest'];
export type TokenResponse = Schemas['TokenResponse'];

export type AccountResponse = Schemas['AccountResponse'];
export type AccountCreate = Schemas['AccountCreate'];
export type AccountUpdate = Schemas['AccountUpdate'];
export type AccountBalanceResponse = Schemas['AccountBalanceResponse'];

export type CategoryResponse = Schemas['CategoryResponse'];
export type CategoryCreate = Schemas['CategoryCreate'];
export type CategoryUpdate = Schemas['CategoryUpdate'];

export type TransactionResponse = Schemas['TransactionResponse'];
export type TransactionCreate = Schemas['TransactionCreate'];
export type TransactionUpdate = Schemas['TransactionUpdate'];
export type TransferCreate = Schemas['TransferCreate'];
export type TransferResponse = Schemas['TransferResponse'];

export type BudgetResponse = Schemas['BudgetResponse'];
export type BudgetCreate = Schemas['BudgetCreate'];
export type BudgetUpdate = Schemas['BudgetUpdate'];
export type BudgetStatusResponse = Schemas['BudgetStatusResponse'];
export type BudgetPortfolioStatus = Schemas['BudgetPortfolioStatus'];

export type ExchangeRateResponse = Schemas['ExchangeRateResponse'];
export type ExchangeRateCreate = Schemas['ExchangeRateCreate'];
export type ResolvedRateResponse = Schemas['ResolvedRateResponse'];

export type InvestmentResponse = Schemas['InvestmentResponse'];
export type InvestmentCreate = Schemas['InvestmentCreate'];
export type InvestmentUpdate = Schemas['InvestmentUpdate'];
export type InvestmentReturnsResponse = Schemas['InvestmentReturnsResponse'];
export type ValuationResponse = Schemas['ValuationResponse'];
export type ValuationCreate = Schemas['ValuationCreate'];

export type NetWorthResponse = Schemas['NetWorthResponse'];
export type NetWorthHistoryResponse = Schemas['NetWorthHistoryResponse'];
export type CashFlowResponse = Schemas['CashFlowResponse'];
export type CategoryBreakdownResponse = Schemas['CategoryBreakdownResponse'];

export type RecurringRuleResponse = Schemas['RecurringRuleResponse'];
export type RecurringRuleCreate = Schemas['RecurringRuleCreate'];
export type RecurringRuleUpdate = Schemas['RecurringRuleUpdate'];
export type RecurringRunResponse = Schemas['RecurringRunResponse'];

export type CsvImportRequest = Schemas['CsvImportRequest'];
export type CsvImportResult = Schemas['CsvImportResult'];
export type CsvImportRowError = Schemas['CsvImportRowError'];
export type CsvColumnMapping = Schemas['CsvColumnMapping'];
export type FullExportResponse = Schemas['FullExportResponse'];

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export type AccountType = Schemas['AccountType'];

export type CategoryKind = Schemas['CategoryKind'];

export type TransactionType = Schemas['TransactionType'];

export type RecurrenceFrequency = Schemas['RecurrenceFrequency'];

export type InvestmentType = Schemas['InvestmentType'];

export type RatePeriod = Schemas['RatePeriod'];

export type Compounding = Schemas['Compounding'];

export type BudgetStatus = Schemas['BudgetStatus'];
