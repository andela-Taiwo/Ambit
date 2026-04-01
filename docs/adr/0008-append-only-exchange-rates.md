# 8. Exchange rates are append-only observations

- **Status**: Accepted
- **Date**: 2026-10-27

## Context

Multi-currency net worth is only trustworthy if every converted figure can be
traced to a rate, a source and a timestamp. A guessed or silently stale rate is
worse than a failed report.

## Decision

- `exchange_rates` stores one observation per `(base, quote, as_of, source)` and
  is never updated in place; a correction is a new row with a later `as_of`.
- `rate` means one unit of `base` buys `rate` units of `quote`. Resolution uses
  the newest observation at or before the requested instant, falls back to the
  inverse pair, and raises `MissingRateError` when neither exists.
- Manual rates are user-scoped; provider rates (`user_id IS NULL`) are shared.
  A user's own observation always wins, so one tenant cannot alter another's
  numbers.
- Conversion math is `Decimal` with one explicit `ROUND_HALF_EVEN` quantize at
  the target currency's minor unit. Rates used are returned alongside amounts.
- The scheduled fetch job is opt-in and idempotent. A provider failure exits
  non-zero and leaves existing observations intact, so the last good rate
  remains resolvable.

## Consequences

- Reports fail with a 422 naming the pair and date rather than dropping a
  holding or inventing a rate.
- Totals are the sum of individually rounded components, so every component is
  auditable against the returned rate.
