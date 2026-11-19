# 15. Browser money formatting never divides through a float

- **Status**: Accepted
- **Date**: 2026-10-27

## Context

The API returns integer minor units. `minor / 100` is safe for small amounts but
loses cents once values exceed the float-exact integer range; later formatting
cannot recover the lost precision.

## Decision

- `src/lib/money.ts` splits the integer into major and fractional parts using
  integer arithmetic, then uses `Intl.NumberFormat.formatToParts` only for the
  currency symbol, grouping and placement.
- User input is parsed with a string-based decimal parser into minor units. It
  rejects excess precision and values beyond the backend's `10^15` guard rather
  than rounding.
- Inputs accept thousands separators; server amounts are always sent as decimal
  strings, never JSON floats.

## Consequences

- Display and parse round-trip exactly for every supported currency, including
  zero- and three-decimal currencies.
- Intl remains responsible for locale presentation without becoming responsible
  for arithmetic.
