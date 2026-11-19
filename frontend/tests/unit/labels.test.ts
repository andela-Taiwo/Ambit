import { describe, expect, it } from 'vitest';

import {
  accountTypeLabels,
  budgetStatusLabels,
  budgetStatusTone,
  categoryKindLabels,
  frequencyLabels,
  transactionTypeLabels,
  valueSourceLabels,
} from '@/lib/labels';

describe('label maps', () => {
  it('exposes labels for every enum value', () => {
    expect(accountTypeLabels.investment).toBe('Investment');
    expect(transactionTypeLabels.transfer).toBe('Transfer');
    expect(categoryKindLabels.income).toBe('Income');
    expect(frequencyLabels.yearly).toBe('Yearly');
    expect(valueSourceLabels.valuation).toBe('Valuation');
    expect(budgetStatusLabels.over).toBe('Over budget');
  });

  it('maps statuses to tones', () => {
    expect(budgetStatusTone('on_track')).toBe('success');
    expect(budgetStatusTone('warning')).toBe('warning');
    expect(budgetStatusTone('over')).toBe('danger');
  });
});
