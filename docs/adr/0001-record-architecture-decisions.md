# 1. Record architecture decisions

- **Status**: Accepted
- **Date**: 2026-09-02

## Context

The plan (Section 14) names solo-maintainer bus factor as a key risk, mitigated
by "documentation-as-you-go". Decisions made once and forgotten are the most
expensive kind to revisit.

## Decision

We record architecturally significant decisions as ADRs in `docs/adr/`,
numbered sequentially, in the Context / Decision / Consequences format. An ADR
is added in the same PR as the change it describes.

## Consequences

- Future changes have a written rationale to argue against, not just code.
- ADRs are immutable once accepted; a reversal is a new ADR superseding the old.
