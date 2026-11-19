# 6. Transfers are stored as two linked legs

- **Status**: Accepted
- **Date**: 2026-09-02

## Context

A transfer moves money between two of the user's own accounts. Modelling it as
a single row with `from`/`to` columns makes every balance query special-case
that row, and makes it easy to write reporting code that accidentally counts a
transfer as income or spending.

## Decision

A transfer is written as **two `Transaction` rows** sharing a
`transfer_group_id`: a negative leg debiting the source and a positive leg
crediting the destination. Both are created in one database transaction, and
deleting either deletes both. Cross-currency transfers are **rejected** until
Phase 4 introduces exchange rates.

## Consequences

- Balances stay a single `SUM(signed_amount_minor)` per account, with no
  special cases.
- The pair always nets to zero, so a transfer can never create or destroy
  value — enforced by a domain unit test.
- Transfer legs are not individually editable; correcting one means deleting
  and recreating the pair, which keeps the ledger balanced by construction.
- Phase 3 budgeting must exclude `transaction_type = transfer` from spend
  calculations, since moving money is not spending it.
