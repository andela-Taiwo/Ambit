# 4. Money is stored as integer minor units

- **Status**: Accepted
- **Date**: 2026-09-02

## Context

Binary floating point cannot represent decimal fractions like 0.10 exactly.
In a ledger, the resulting drift accumulates and produces balances that are
wrong in ways users notice. Currencies also differ in how they subdivide: most
use two decimal places, JPY uses none, BHD and KWD use three.

## Decision

- Amounts are stored as `BigInteger` **minor units** (pence, kobo, cents)
  alongside an explicit ISO 4217 currency code. `Float` is never used.
- The API accepts and returns decimal *strings*, converted at the boundary via
  `Decimal` in `app/domain/money.py`.
- Conversion **rejects** any amount with more precision than the currency
  allows (`0.005 GBP`) rather than rounding it. Silently losing a fraction of a
  unit is a correctness bug, not a display concern.
- `amount_minor` holds a positive magnitude; direction lives in
  `transaction_type` and in a derived `signed_amount_minor`. A database
  `CHECK` constraint enforces `amount_minor > 0` and
  `abs(signed_amount_minor) = amount_minor`.

## Consequences

- Every amount crossing the API boundary must be converted explicitly; there
  is no implicit float path to fall into.
- Balance queries are a plain integer `SUM`, exact by construction.
- Zero-decimal and three-decimal currencies work without special-casing at
  call sites, because the exponent is looked up per currency.
