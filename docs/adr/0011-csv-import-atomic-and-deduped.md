# 11. CSV import is atomic and de-duplicated

- **Status**: Accepted
- **Date**: 2026-10-27

## Context

Bank statements are messy and users retry imports. A partially imported
statement is harder to reconcile than a clear rejection, and duplicate rows
corrupt every downstream report.

## Decision

- The whole file is parsed and validated before any write. Any bad row rejects
  the import with HTTP 422 and row-numbered errors; nothing is written.
- Amounts accept currency symbols, thousands separators, parenthesised negatives
  and a trailing sign, and are converted with `Decimal`; over-precise values are
  rejected rather than rounded.
- Income/expense is taken from an explicit type column when mapped, otherwise
  from the sign using a configurable convention.
- De-duplication uses a per-user hash. A mapped bank reference hashes alone;
  otherwise the canonical row plus an occurrence ordinal is hashed, preserving
  identical rows within a file while making a re-import a no-op. A partial
  unique index `(user_id, import_hash)` enforces this in the database.
- `dry_run` performs the same validation/de-duplication and reports counts
  without writing.
- The full export (`GET /api/v1/export`) contains only the caller's own rows and
  never includes password or token hashes.

## Consequences

- Import responses are small and actionable; the frontend does not need to
  re-parse the file to find bad rows.
- Content de-duplication without a bank reference can treat an identical
  transaction in a later file as a duplicate. Users importing overlapping
  statements should map the reference column.
