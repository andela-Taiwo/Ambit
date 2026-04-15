# 12. Investment accounts are containers, not cash

- **Status**: Accepted
- **Date**: 2026-10-27

## Context

An investment account can hold both ledger transactions and `Investment`
holdings. Counting the account's ledger balance *and* the holding's value would
double count the same money when a transfer funds a purchase.

## Decision

- Net worth counts:
  - the ledger balances of **non-investment** accounts, plus
  - the current value of every investment (snapshot, accrual or principal).
- Investment-account ledger balances are excluded from net worth. The holding is
  the source of truth for money inside that container.
- If an investment account holds uninvested cash, model it in a separate cash
  account until it is actually placed in a holding. The UI/report can show the
  account itself, but it does not add to the total twice.

## Consequences

- Funding a purchase with a transfer no longer changes net worth: cash leaves a
  counted account and appears as a holding at the same value.
- Investment accounts with only cash and no holdings contribute zero until a
  holding is recorded. This is explicit and avoids a silent overstatement.
