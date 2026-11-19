import { describe, expect, it } from 'vitest';

import {
  currencyExponent,
  formatMinorDecimal,
  formatMoney,
  minorToInput,
  parseAmountToMinor,
} from '@/lib/money';

describe('currency exponents', () => {
  it('knows two-decimal currencies', () => {
    expect(currencyExponent('GBP')).toBe(2);
    expect(currencyExponent('ngn')).toBe(2);
  });

  it('knows zero-decimal currencies', () => {
    expect(currencyExponent('JPY')).toBe(0);
  });

  it('knows three-decimal currencies', () => {
    expect(currencyExponent('KWD')).toBe(3);
  });

  it('falls back to two decimals for an unknown code', () => {
    expect(currencyExponent('ZZZ')).toBe(2);
  });
});

describe('formatMoney', () => {
  it('formats integer minor units without floating-point division', () => {
    expect(formatMoney(123_456, 'GBP')).toContain('1,234.56');
  });

  it('formats zero-decimal currencies without a decimal point', () => {
    expect(formatMoney(1_234, 'JPY')).toContain('1,234');
    expect(formatMoney(1_234, 'JPY')).not.toContain('.');
  });

  it('formats three-decimal currencies', () => {
    expect(formatMoney(1_234, 'KWD')).toContain('1.234');
  });

  it('formats negative amounts', () => {
    expect(formatMoney(-2_499, 'GBP')).toContain('24.99');
    expect(formatMoney(-2_499, 'GBP')).toMatch(/^-|−/);
  });

  it('preserves a value beyond float-safe cents', () => {
    // 10,000,000,000,000.01 would lose the cent if divided as a float first.
    expect(formatMoney(1_000_000_000_000_001, 'GBP')).toContain('10,000,000,000,000.01');
  });
});

describe('formatMinorDecimal', () => {
  it('renders a bare decimal string', () => {
    expect(formatMinorDecimal(123_456, 'GBP')).toBe('1234.56');
    expect(formatMinorDecimal(123_456, 'JPY')).toBe('123456');
    expect(formatMinorDecimal(-50, 'GBP')).toBe('-0.50');
  });
});

describe('parseAmountToMinor', () => {
  it('parses a plain decimal exactly', () => {
    expect(parseAmountToMinor('1234.56', 'GBP')).toBe(123_456);
  });

  it('accepts thousands separators and surrounding whitespace', () => {
    expect(parseAmountToMinor(' 1,234.50 ', 'GBP')).toBe(123_450);
  });

  it('accepts negative amounts', () => {
    expect(parseAmountToMinor('-10.05', 'GBP')).toBe(-1_005);
  });

  it('rejects more precision than the currency supports', () => {
    expect(parseAmountToMinor('10.005', 'GBP')).toBeNull();
  });

  it('accepts zero-decimal values only as whole units', () => {
    expect(parseAmountToMinor('100', 'JPY')).toBe(100);
    expect(parseAmountToMinor('100.5', 'JPY')).toBeNull();
  });

  it('pads fractional digits to the currency exponent', () => {
    expect(parseAmountToMinor('10.5', 'GBP')).toBe(1_050);
  });

  it('rejects malformed values', () => {
    expect(parseAmountToMinor('', 'GBP')).toBeNull();
    expect(parseAmountToMinor('abc', 'GBP')).toBeNull();
    expect(parseAmountToMinor('1.2.3', 'GBP')).toBeNull();
    expect(parseAmountToMinor('NaN', 'GBP')).toBeNull();
  });

  it('rejects amounts beyond the backend safe bound', () => {
    expect(parseAmountToMinor('99999999999999999', 'GBP')).toBeNull();
  });
});

describe('minorToInput', () => {
  it('renders an editable decimal string', () => {
    expect(minorToInput(123_456, 'GBP')).toBe('1234.56');
    expect(minorToInput(0, 'JPY')).toBe('0');
    expect(minorToInput(-50, 'GBP')).toBe('-0.50');
  });
});
