# 9. Interest accrues by calendar month, not ACT/365

- **Status**: Accepted
- **Date**: 2026-10-27

## Context

The reference product is a Naira fixed deposit: ₦10,000,000 at 24% per annum
pays ₦200,000 per month. An ACT/365 shortcut gives ₦197,260 for a 30-day month,
which does not match the product's stated terms.

## Decision

- Rates are stored as `Decimal` percentages with an explicit `rate_period`
  (`annual` or `monthly`) and `compounding` (`simple` or `monthly`).
- Full calendar months accrue at the monthly rate (`annual / 12`). A partial
  month accrues pro rata by days in that calendar month, with the anchor day
  clamped for short months (31 Jan + 1 month = 28/29 Feb).
- Compounding adds interest at each month boundary; a partial month then accrues
  simple interest on the resulting balance.
- Accrual stops at `maturity_date`.
- Valuation snapshots (and their `source`) override accrual. Without a snapshot,
  fixed-rate holdings report an `accrual` basis; market-priced holdings report
  `principal`, never an invented price.
- Every monetary result is rounded once, half-even, to integer minor units.

## Consequences

- The worked example is a unit test, not an approximation
  (`tests/unit/test_investments.py`).
- `value_source` is explicit in every returns/report response.
