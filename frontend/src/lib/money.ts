/**
 * Money helpers.
 *
 * Amounts cross the API as integer minor units. Formatting is done by
 * splitting the integer into major/minor parts and using Intl only for
 * grouping and currency placement, so display never introduces a floating
 * point rounding error.
 */

const EXPONENTS: Readonly<Record<string, number>> = {
  GBP: 2,
  USD: 2,
  EUR: 2,
  NGN: 2,
  CAD: 2,
  AUD: 2,
  CHF: 2,
  ZAR: 2,
  GHS: 2,
  KES: 2,
  JPY: 0,
  KRW: 0,
  XOF: 0,
  XAF: 0,
  BHD: 3,
  KWD: 3,
  TND: 3,
  OMR: 3,
};

/** Mirrors the backend's BigInteger guard. */
export const MAX_MINOR_UNITS = 10 ** 15;

export const SUPPORTED_CURRENCIES = Object.freeze(Object.keys(EXPONENTS).sort());

export const currencyExponent = (currency: string): number =>
  EXPONENTS[currency.toUpperCase()] ?? 2;

export const normaliseCurrency = (currency: string): string => currency.trim().toUpperCase();

export const formatMinorDecimal = (minor: number, currency: string): string => {
  const exponent = currencyExponent(currency);
  const scale = 10 ** exponent;
  const sign = minor < 0 ? '-' : '';
  const absolute = Math.abs(minor);
  const major = Math.floor(absolute / scale);
  if (exponent === 0) {
    return `${sign}${String(major)}`;
  }
  const fraction = String(absolute - major * scale).padStart(exponent, '0');
  return `${sign}${String(major)}.${fraction}`;
};

export const minorToInput = formatMinorDecimal;

export const formatMoney = (minor: number, currency: string): string => {
  const code = normaliseCurrency(currency);
  const exponent = currencyExponent(code);
  const scale = 10 ** exponent;
  const absolute = Math.abs(minor);
  const major = Math.floor(absolute / scale);
  const fraction = String(absolute - major * scale).padStart(exponent, '0');

  const formatter = new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: code,
    minimumFractionDigits: exponent,
    maximumFractionDigits: exponent,
  });
  const majorFormatted = new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 0,
  }).format(major);

  const formatted = formatter
    .formatToParts(0)
    .map((part) => {
      if (part.type === 'integer') return majorFormatted;
      if (part.type === 'fraction') return fraction;
      if (part.type === 'minusSign') return '';
      return part.value;
    })
    .join('');

  return minor < 0 ? `-${formatted}` : formatted;
};

export const formatPercent = (value: string | number): string => {
  const parsed = typeof value === 'number' ? value : Number.parseFloat(value);
  if (!Number.isFinite(parsed)) return '—';
  return `${parsed.toFixed(2)}%`;
};

/**
 * Parse an editable decimal amount into integer minor units, or null.
 *
 * Deliberately string-based: `Number('0.1') * 100` is 10.000000000000002, and
 * silently rounding that would defeat the backend's exactness guarantees.
 */
export const parseAmountToMinor = (input: string, currency: string): number | null => {
  const exponent = currencyExponent(currency);
  const normalised = input.trim().replaceAll(',', '');
  const match = /^([+-]?)(\d+)(?:\.(\d+))?$/.exec(normalised);
  if (match === null) return null;

  const sign = match[1] === '-' ? -1 : 1;
  const whole = match[2] ?? '0';
  const rawFraction = match[3] ?? '';
  if (rawFraction.length > exponent) return null;
  const fraction = rawFraction.padEnd(exponent, '0');

  const scale = 10n ** BigInt(exponent);
  const minor = BigInt(whole) * scale + BigInt(fraction === '' ? '0' : fraction);
  if (minor > BigInt(MAX_MINOR_UNITS)) return null;

  const result = sign * Number(minor);
  return Number.isSafeInteger(result) ? result : null;
};
