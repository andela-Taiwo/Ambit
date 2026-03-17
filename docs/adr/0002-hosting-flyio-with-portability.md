# 2. Host on Fly.io initially, retaining self-hosting portability

- **Status**: Accepted
- **Date**: 2026-09-02

## Context

Plan Section 15 left the hosting provider open. The stated intent is to run on
Fly.io now but move to a self-managed server later. Committing to
provider-specific primitives (managed queues, proprietary runtimes, platform
auth) would make that move a rewrite rather than a migration.

## Decision

Deploy to Fly.io for staging and production for now. To keep the eventual
self-hosted move cheap:

- The applications are **plain Docker containers** listening on a port and
  configured entirely through environment variables (12-factor). Nothing in
  `backend/app` or `frontend/src` references Fly.
- Terraform is structured as `infra/terraform/modules/app` (a provider-neutral
  interface: image, tag, env vars, region) consumed by thin per-environment
  roots. Changing host means reimplementing that one module.
- Postgres is reached only via a standard DSN, so it can be a Fly Postgres
  cluster today and a self-managed instance later.
- Images are published to GHCR, not a provider registry, so any host can pull
  the identical artifact.

## Consequences

- Fly-specific resources are confined to one module; the blast radius of a
  host change is small and reviewable.
- Some Fly conveniences are deliberately unused where they would create lock-in.
- The self-hosted target will need its own module plus a documented runbook
  (backups, TLS, monitoring) that Fly currently provides.
