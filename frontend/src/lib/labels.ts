import type { AccountType, CategoryKind, RecurrenceFrequency, TransactionType } from '@/api/types';

export const accountTypeLabels: Record<AccountType, string> = {
  cash: 'Cash',
  current: 'Current account',
  savings: 'Savings',
  credit_card: 'Credit card',
  investment: 'Investment',
};

export const transactionTypeLabels: Record<TransactionType, string> = {
  income: 'Income',
  expense: 'Expense',
  transfer: 'Transfer',
};

export const categoryKindLabels: Record<CategoryKind, string> = {
  income: 'Income',
  expense: 'Expense',
};

export const frequencyLabels: Record<RecurrenceFrequency, string> = {
  daily: 'Daily',
  weekly: 'Weekly',
  monthly: 'Monthly',
  yearly: 'Yearly',
};

export const budgetStatusLabels: Record<'on_track' | 'warning' | 'over', string> = {
  on_track: 'On track',
  warning: 'Near limit',
  over: 'Over budget',
};

export const budgetStatusTone = (
  status: 'on_track' | 'warning' | 'over',
): 'success' | 'warning' | 'danger' =>
  status === 'on_track' ? 'success' : status === 'warning' ? 'warning' : 'danger';

export const valueSourceLabels: Record<'valuation' | 'accrual' | 'principal', string> = {
  valuation: 'Valuation',
  accrual: 'Accrued',
  principal: 'Cost',
};
