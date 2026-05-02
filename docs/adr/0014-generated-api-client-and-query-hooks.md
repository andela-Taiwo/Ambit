# 14. API types are generated; server state lives in TanStack Query

- **Status**: Accepted
- **Date**: 2026-10-27

## Context

The backend OpenAPI schema is the contract. Hand-written response types drift
silently, and duplicating server data into a global store causes stale views.

## Decision

- `yarn generate:api` runs `openapi-typescript` against `backend/openapi.json`
  into `src/api/generated/schema.ts`; that directory is committed and excluded
  from lint/coverage because it is generated.
- `src/api/types.ts` exposes small aliases over the generated components.
- `src/api/endpoints.ts` is the only place that builds URLs/request bodies.
- `src/api/hooks.ts` wraps queries and mutations, with explicit query keys and
  targeted invalidation after writes.
- Zustand holds only session/UI state (Auth store). No server entity is copied
  into it.

## Consequences

- An API contract change is a type error in CI, not a runtime surprise.
- Mutations invalidate only affected resources (accounts, transactions,
  budgets, reports, investments, recurring rules), keeping refetches predictable.
