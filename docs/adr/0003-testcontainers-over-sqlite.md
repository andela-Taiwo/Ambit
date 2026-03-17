# 3. Integration tests run against real Postgres

- **Status**: Accepted
- **Date**: 2026-09-02

## Context

Substituting SQLite for Postgres in tests is fast but hides dialect-specific
behaviour. This application stores money and will rely on `NUMERIC`, timezone-
aware timestamps, and database-level constraints, all of which differ between
the two engines.

## Decision

Integration tests start a real `postgres:16-alpine` container via
Testcontainers, both locally and in CI. Unit tests remain database-free.

## Consequences

- Tests catch dialect bugs before staging.
- The test suite requires a working Docker daemon.
- Integration tests are slower than in-memory equivalents, which is why the
  pyramid (plan Section 8) keeps them at ~30% of the suite.
