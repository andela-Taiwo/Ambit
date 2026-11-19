import { describe, expect, it } from 'vitest';

import {
  addMonthsToMonth,
  currentMonth,
  formatDate,
  monthLabel,
  monthStartIso,
  nextMonthStartIso,
  todayIso,
} from '@/lib/dates';

describe('date helpers', () => {
  it('formats an ISO date for display', () => {
    expect(formatDate('2026-02-01')).toMatch(/1 Feb 2026/);
  });

  it('returns a local ISO date for today', () => {
    expect(todayIso()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('returns the current month key', () => {
    expect(currentMonth()).toMatch(/^\d{4}-\d{2}$/);
  });

  it('labels a month key', () => {
    expect(monthLabel('2026-02')).toBe('February 2026');
  });

  it('turns a month key into its first day', () => {
    expect(monthStartIso('2026-02')).toBe('2026-02-01');
  });

  it('turns a month key into the next month start', () => {
    expect(nextMonthStartIso('2026-02')).toBe('2026-03-01');
    expect(nextMonthStartIso('2026-12')).toBe('2027-01-01');
  });

  it('adds months across year boundaries', () => {
    expect(addMonthsToMonth('2026-01', 1)).toBe('2026-02');
    expect(addMonthsToMonth('2026-01', -1)).toBe('2025-12');
    expect(addMonthsToMonth('2026-12', 1)).toBe('2027-01');
  });
});
