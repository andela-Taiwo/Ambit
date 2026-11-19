# 7. Budget periods are half-open calendar months

- **Status**: Accepted
- **Date**: 2026-10-27

## Context

Budget-vs-actual is the highest-risk area for off-by-one bugs: a transaction on
the last day of a month must belong to exactly one period, and rollover must
carry a signed balance without drifting.

## Decision

- A budget applies to calendar months. `starts_on` is the first day of its first
  month; `ends_on`, when present, is the first day of the first month it does
  **not** apply to. Periods are half-open `[start, end)`.
- The database enforces month alignment (`EXTRACT(DAY …) = 1`) and
  non-negative limits; the API rejects mid-month boundaries before that.
- Spend is aggregated by the transaction date, includes descendant categories,
  excludes transfers and income, and is converted to the budget currency with a
  recorded exchange rate.
- Rollover, when enabled, computes the full chain since `starts_on`:
  `carry = Σ(limit − spend)` for prior months. Overspending produces a negative
  carry; it is never clamped to zero, because hiding a bad month is worse than
  showing it.
- A category may have one *active* budget at a time, enforced by a partial
  unique index; archived budgets remain as history.

## Consequences

- Period boundaries are testable pure functions (`app/domain/budgets.py`).
- Changing a budget's amount reinterprets prior months' rollover. This is
  deliberate in v1; per-period limit history would be the next refinement.
