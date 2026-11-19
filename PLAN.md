# Personal Finance & Investment Tracker — Project Plan

**Status:** Draft v1.0
**Owner:** Taiwo Sokunbi
**Last updated:** 2026-09-02

## 1. Purpose & Scope

Build a fullstack, production-grade personal finance application covering three
pillars:

1. **Expense management** — categorized transactions, recurring bills, receipts.
2. **Budgeting** — monthly/rolling budgets per category, budget-vs-actual tracking.
3. **Investment tracking** — multi-currency holdings (e.g. Naira fixed-income
   products alongside GBP/USD accounts), interest/return accrual, valuation over
   time, and consolidated net-worth reporting across currencies.

This is treated as a real engineering project, not a prototype: every phase
below ends in shippable, tested, deployable software, and CI/CD plus
multi-environment support are established in Phase 0, not bolted on later.

**Out of scope for v1** (revisit post-launch): live market-data feeds for
tradeable securities (stocks/ETFs), multi-user/household sharing, native mobile
apps. The API is designed so none of these are precluded later.

## 2. Guiding Principles

These translate the constraints given into concrete engineering rules the team
(or future-me) is held to for the life of the project:

- **TDD, always.** No production code is written before a failing test exists
  for it. Red → Green → Refactor is the unit of work, enforced by code review
  and by CI coverage gates, not just convention.
- **No shortcuts.** No `# type: ignore` / `any` escape hatches without a
  documented reason, no `Base.metadata.create_all()` in place of real
  migrations, no hardcoded secrets or config, no silently-swallowed
  exceptions, no TODO left unaddressed in a merged PR without a tracked issue.
- **Environment parity from day one.** Local, CI, staging, and production run
  the same container images and the same migration path; the only thing that
  changes between them is configuration (12-factor).
- **CI/CD is infrastructure, not an afterthought.** Phase 0 ships a working
  pipeline (lint, type-check, test, build) before a single feature is built.
  Deploy automation matures in later phases, but the pipeline itself exists
  from commit one.
- **Type safety end to end.** Strict `mypy` on the backend, strict TypeScript
  (`strict: true`, no implicit `any`) on the frontend, and a single source of
  truth for API contracts (OpenAPI generated from FastAPI, consumed by a
  generated TS client) so the two sides cannot silently drift apart.
- **Everything reviewable.** Small PRs, one logical change each, CI green
  before merge, no direct pushes to `main`.

## 3. Tech Stack & Rationale

| Layer | Choice | Rationale |
|---|---|---|
| Backend framework | **FastAPI** (latest 0.13x line), Python 3.12+ | Async-first, Pydantic v2 validation, auto OpenAPI docs. Pinned via lockfile, kept current via Renovate/Dependabot rather than frozen. |
| ORM / migrations | SQLAlchemy 2.0 (async) + Alembic | Explicit, reviewable migrations; async engine matches FastAPI's async request path. |
| Validation | Pydantic v2 | Already FastAPI's native layer; separate request/response schemas from ORM models. |
| Database | PostgreSQL 16+ | Strong transactional guarantees for financial data, native `NUMERIC` type (never floats for money), row-level constraints. |
| Auth | Custom JWT (access + rotating refresh tokens), Argon2 password hashing | Full control over token lifecycle; avoids vendor lock-in for a personal-finance app where auth is core, not incidental. |
| Backend testing | pytest, pytest-asyncio, httpx `AsyncClient`, Testcontainers (real Postgres in CI), polyfactory (test data factories), pytest-cov | Integration tests run against a real Postgres, not SQLite, to catch dialect-specific bugs early. |
| Backend tooling | `uv` (dependency mgmt + venv), Ruff (lint + format), mypy --strict | Fast, single-tool dependency management; Ruff replaces Black+isort+flake8. |
| Frontend framework | **React 19** + TypeScript, Vite | Current stable React; Vite for fast dev/build over CRA (unmaintained). |
| Frontend data layer | TanStack Query + a generated TS client (openapi-typescript-codegen or orval) from the backend's OpenAPI schema | Removes hand-written fetch/type duplication; contract drift becomes a build failure, not a runtime bug. |
| Frontend state | Zustand (local/UI state only — server state stays in TanStack Query) | Avoids the common anti-pattern of duplicating server state into a global store. |
| Styling | Tailwind CSS + headless UI primitives (Radix) | Fast to build accessible components without hand-rolling ARIA behavior. |
| Frontend testing | Vitest + React Testing Library (unit/component), Playwright (E2E) | RTL enforces testing behavior over implementation; Playwright covers real browser flows against a running stack. |
| Frontend tooling | ESLint (typescript-eslint), Prettier, `tsc --noEmit` in CI | Type errors and lint fail the build, not just the editor. |
| Containerization | Docker (multi-stage builds), docker-compose for local dev | Same image runs locally, in CI, and in every deployed environment. |
| CI | GitHub Actions | Matrix builds, environment protection rules, first-class Docker support. |
| IaC | Terraform | Environments (staging/prod) are defined as code and reproducible, regardless of which host ends up running them. |
| Hosting (recommended start) | Fly.io or Render (Postgres + container app) | Right-sized for a personal-scale app; Docker/Terraform layer stays portable to AWS/GCP later without a rewrite. |
| Error tracking / logging | Sentry (both apps), structlog (JSON logs, backend) | Structured logs and real error tracking from day one, not `print()` debugging. |
| Secrets | GitHub Environments (per-stage secrets) + provider's secret manager in prod | No secret ever committed; `.env.example` documents required keys with dummy values. |

## 4. High-Level Architecture

```
                        ┌─────────────────────┐
                        │   React + TS SPA     │
                        │  (Vite, TanStack Q)  │
                        └──────────┬───────────┘
                                   │ HTTPS / JSON (OpenAPI contract)
                        ┌──────────▼───────────┐
                        │   FastAPI backend     │
                        │  (async, JWT auth)    │
                        └──────────┬───────────┘
                                   │ SQLAlchemy (async)
                        ┌──────────▼───────────┐
                        │     PostgreSQL        │
                        └───────────────────────┘

Cross-cutting: structured logging + Sentry, Alembic migrations,
Terraform-managed infra per environment, GitHub Actions for CI/CD.
```

Single monorepo (`/backend`, `/frontend`, `/infra`, `/.github`) rather than
split repos — this is a two-surface app maintained by one team; a monorepo
keeps API-contract changes and their consuming frontend changes in one PR.

## 5. Repository Structure

```
Ambit/
├── backend/
│   ├── app/
│   │   ├── api/            # routers, versioned (api/v1/...)
│   │   ├── core/           # settings, security, logging config
│   │   ├── domain/         # entities, business logic (framework-agnostic)
│   │   ├── db/             # SQLAlchemy models, session, migrations (alembic/)
│   │   ├── schemas/        # Pydantic request/response models
│   │   └── main.py
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/    # Testcontainers-backed, real Postgres
│   │   └── conftest.py
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/             # generated client + query hooks
│   │   ├── features/        # budgets/, transactions/, investments/, ...
│   │   ├── components/      # shared design-system components
│   │   └── app/             # routing, providers, shell
│   ├── tests/
│   │   ├── unit/
│   │   └── e2e/             # Playwright specs
│   ├── package.json
│   └── Dockerfile
├── infra/
│   ├── terraform/
│   │   ├── modules/
│   │   ├── staging/
│   │   └── production/
│   └── docker-compose.yml   # local dev: db + backend + frontend
├── .github/
│   └── workflows/
│       ├── ci.yml           # lint, typecheck, test, build — every PR
│       ├── deploy-staging.yml
│       └── deploy-production.yml
├── docs/
│   └── adr/                 # architecture decision records
└── plan.md                  # this document
```

## 6. Environments & Configuration Strategy

| Environment | Purpose | Data | Deploy trigger |
|---|---|---|---|
| **Local** | Development | docker-compose Postgres, seeded fixtures | manual (`docker compose up`) |
| **CI** | Test execution | ephemeral Testcontainers Postgres, destroyed per run | every PR + every push to `main` |
| **Staging** | Pre-prod validation, mirrors prod topology | anonymized/synthetic data | automatic on merge to `main` |
| **Production** | Live app | real data, backed up | manual approval gate after staging smoke tests pass |

Configuration is environment-variable driven via `pydantic-settings`
(backend) and Vite `import.meta.env` (frontend), validated at startup — the
app refuses to boot with missing/malformed required config rather than
failing silently later. No environment-specific code branches; only
configuration differs.

## 7. CI/CD Strategy (established in Phase 0, matured over time)

- **`ci.yml`** (every PR and push to `main`): matrix job for backend
  (Ruff → mypy --strict → pytest with coverage gate → Docker build) and
  frontend (ESLint → tsc --noEmit → Vitest with coverage gate → Playwright
  smoke tests against a built preview → Docker build). All must pass before
  merge is allowed (branch protection).
- **Security gates in the same pipeline, not a separate afterthought**:
  `pip-audit` / `npm audit`, Dependabot for dependency PRs, `gitleaks` for
  secret scanning.
- **`deploy-staging.yml`**: on merge to `main`, build & push images to GHCR,
  `terraform plan/apply` against the staging workspace, run Alembic
  migrations, run Playwright smoke suite against the live staging URL.
- **`deploy-production.yml`**: triggered by a version tag; requires a GitHub
  Environment manual approval; applies the same image (promoted from
  staging, never rebuilt) via Terraform, runs migrations with a rollback
  plan documented, then runs smoke tests.
- **Rollback**: every deploy records the previous image tag; rollback is a
  one-command re-deploy of that tag, not a git revert-and-rebuild.

## 8. Testing Strategy (TDD is the default workflow, not a phase)

Every ticket/feature is written test-first:

1. Write a failing test at the appropriate level (unit for domain logic,
   integration for a full request → DB round trip, component test for UI
   behavior, E2E for a critical user journey).
2. Write the minimum code to pass it.
3. Refactor with the test as a safety net.
4. CI enforces this indirectly via coverage gates — a PR that drops coverage
   below threshold fails, so untested code cannot merge.

Test pyramid targets:

- **Unit tests (60%)**: domain logic (budget math, interest accrual,
  currency conversion), pure functions, isolated from DB/network.
- **Integration tests (30%)**: FastAPI routes against a real Postgres
  (Testcontainers), full request/response cycle including auth.
- **E2E tests (10%)**: Playwright, covering the critical paths only
  (sign-up/login, add transaction, set a budget, add an investment and see
  it reflected in net worth) — kept small deliberately since E2E is the
  slowest, most brittle layer.

Coverage gates: **≥90% backend, ≥85% frontend**, enforced in CI, reviewed
per-PR, not just at merge time. Mutation testing (`mutmut`) is a stretch
goal for Phase 7 to validate the tests are actually asserting behavior, not
just executing lines.

## 9. Domain Model (initial cut — refined in Phase 1/3/4)

- **User** — auth identity, base currency preference.
- **Account** — cash/bank/investment "container" a transaction or holding
  belongs to; has a currency.
- **Category** — expense/income classification, user-definable, supports
  hierarchy (e.g. `Transport > Fuel`).
- **Transaction** — amount (stored as integer minor units, never float),
  currency, category, account, date, type (income/expense/transfer), notes.
- **Budget** — per-category monthly (or custom period) limit, rollover
  option, compared against actual transactions for the period.
- **RecurringRule** — generates transactions on a schedule (rent, salary,
  subscriptions).
- **Investment** — a holding within an investment Account: principal,
  currency, and either (a) a fixed/expected-rate instrument (e.g. a Naira
  fixed-income product with a stated annual/monthly rate — matching the
  kind of investment being tracked today) or (b) a market-priced instrument
  (future: units + price feed).
- **InvestmentValuationSnapshot** — periodic recorded value, so net worth
  and returns can be charted over time even for instruments without a live
  price feed.
- **ExchangeRate** — currency pair + rate + timestamp, used to express
  multi-currency accounts/investments in the user's base currency for
  reporting; sourced from a scheduled job hitting a rates API, cached, with
  the source and fetch time always retained (never silently guessed).
- **AuditLog** — append-only record of financial mutations (who/when/what
  changed), since this is money data.

## 10. Security & Compliance Considerations

- Argon2 password hashing; short-lived JWT access tokens + rotating,
  revocable refresh tokens (stored hashed).
- Rate limiting on auth endpoints; account lockout/backoff on repeated
  failures.
- All input validated at the Pydantic boundary; all queries parameterized
  via the ORM (no raw string-built SQL).
- CORS explicitly scoped per environment (no `*` in staging/prod).
- Dependency and secret scanning in CI (Section 7); no secret ever
  committed — `.env.example` only, real values live in GitHub
  Environments/provider secret store.
- TLS everywhere in staging/production; DB encryption at rest via the
  managed provider.
- Financial mutations are append-only at the audit layer even if the
  underlying row is later edited/deleted, so history is reconstructible.

## 11. Observability & Operations

- Structured (JSON) logs via `structlog`, correlation ID per request,
  propagated frontend → backend for traceable error reports.
- Sentry on both apps for error tracking, with source maps uploaded on
  frontend deploy.
- `/health` (liveness) and `/ready` (readiness, checks DB connectivity)
  endpoints from Phase 0, used by the hosting platform and by deploy
  smoke tests.
- Basic uptime monitoring on staging/production URLs.
- Backups: automated daily Postgres backups in production with a tested
  restore procedure (a backup that has never been restored is not a
  backup) — this is a Phase 8 exit criterion, not optional polish.

## 12. Development Phases

Each phase lists its goal, scope, TDD approach, and exit criteria. No phase
is "done" until its exit criteria are met in CI on `main`.

### Phase 0 — Foundations, Environments & CI/CD Skeleton
- **Goal**: A deployable "hello world" full stack with the entire pipeline
  working, before any feature exists.
- **Scope**: Repo scaffold (Section 5); FastAPI app with `/health`/`/ready`;
  React+Vite app with a single authenticated-shell page; Postgres +
  Alembic wired up with one trivial migration; Docker images for both
  apps; `docker-compose.yml` for local dev; `ci.yml` running lint/type/test/
  build for both apps against a real (Testcontainers) Postgres; Terraform
  skeleton for staging; first deploy of the "hello world" app to staging.
- **TDD approach**: Even the health endpoint is written test-first
  (integration test asserting 200 + expected payload) to establish the
  pattern from commit one.
- **Exit criteria**: A PR merged to `main` triggers CI (green) and an
  automatic deploy to staging that responds on `/health`. Branch
  protection enabled. No manual steps required to reproduce the pipeline.

### Phase 1 — Backend Core Domain: Auth, Accounts & Ledger
- **Goal**: The transactional backbone — users can register/log in and
  record income/expense transactions against accounts and categories.
- **Scope**: User model + JWT auth (register/login/refresh/logout);
  Account, Category, Transaction CRUD; money stored as integer minor
  units with currency; Alembic migrations for each; OpenAPI schema
  reviewed for correctness (this becomes the frontend's contract).
- **TDD approach**: Unit tests for domain logic (e.g. amount validation,
  category hierarchy rules) before implementation; integration tests for
  every endpoint (auth required, ownership enforced — user A cannot read
  user B's transactions) before the route is wired up.
- **Exit criteria**: ≥90% backend coverage on this module; auth and ledger
  endpoints deployed to staging; Postman/OpenAPI-driven manual smoke pass.

### Phase 2 — Frontend Foundations: App Shell, Auth Flow & Design System
- **Goal**: A usable authenticated shell the rest of the UI builds on.
- **Scope**: Vite+TS scaffold; TanStack Query + generated API client wired
  to Phase 1's OpenAPI schema; login/register/logout flows; protected
  routing; base design-system components (buttons, forms, tables, modals)
  built accessibly on Radix primitives; transaction list + add-transaction
  form as the first real feature slice, end to end.
- **TDD approach**: RTL component tests for each design-system component
  and form (validation states, loading/error states) written before the
  component; one Playwright E2E test (login → add a transaction → see it
  listed) written before the flow is wired end to end.
- **Exit criteria**: ≥85% frontend coverage; the add-transaction E2E test
  passes against staging in CI.

### Phase 3 — Budgeting Module
- **Goal**: Users can set per-category budgets and see actual-vs-budget.
- **Scope**: Budget model/endpoints (period, category, limit, rollover);
  aggregation query (spend per category per period); frontend budget
  setup UI + a budget-vs-actual view (progress bars, over-budget alerts).
- **TDD approach**: Budget math (rollover calculation, period boundaries,
  over/under status) unit-tested exhaustively before the aggregation
  endpoint is built, since this is the highest-risk-of-off-by-one logic
  in the app.
- **Exit criteria**: Coverage gates hold; a full "create budget → add
  transactions → see accurate status" journey covered by an E2E test.

### Phase 4 — Investment Tracking Module (incl. Multi-Currency)
- **Goal**: Track investments (starting with fixed-rate products like the
  Naira deposits discussed, extensible to market-priced instruments
  later) and express them in the user's base currency.
- **Scope**: Investment + InvestmentValuationSnapshot models; interest
  accrual calculation (monthly/annual rate → projected and realized
  return); ExchangeRate model + a scheduled job fetching/caching rates;
  a "convert to base currency" utility used consistently across reporting;
  frontend investment list, add/edit forms, and a simple returns chart.
- **TDD approach**: Interest-accrual and currency-conversion math are
  pure functions, unit-tested first against known worked examples (e.g.
  the exact ₦10m/24%-annual → ₦200k/month case) before wiring into
  endpoints; integration test for the scheduled rate-fetch job with the
  external call mocked, asserting caching/fallback behavior when the
  rate source is unavailable.
- **Exit criteria**: Coverage gates hold; documented worked-example test
  cases pass; staging deploy includes at least one multi-currency
  investment rendering correctly in the base-currency dashboard.

### Phase 5 — Reporting, Analytics & Net-Worth Dashboard
- **Goal**: Tie the three pillars together into a single net-worth and
  cash-flow view.
- **Scope**: Net worth over time (accounts + investments, base-currency
  normalized); cash-flow report (income vs. expense trend); category
  breakdown charts; CSV export of transactions.
- **TDD approach**: Report-generation logic unit-tested against fixed
  input fixtures with hand-calculated expected output; snapshot/visual
  regression consideration for charts is explicitly deprioritized in
  favor of testing the underlying data the charts render.
- **Exit criteria**: Coverage gates hold; dashboard reflects Phases 1–4
  data correctly in a staging walkthrough.

### Phase 6 — Automation: Recurring Transactions & Import/Export
- **Goal**: Reduce manual data entry.
- **Scope**: RecurringRule model + scheduled job generating transactions;
  CSV import (bank statement) with column mapping and de-duplication;
  full data export (GDPR-style "take your data with you," useful even
  for a personal app as a backup mechanism).
- **TDD approach**: De-duplication and schedule-generation logic
  unit-tested against edge cases (leap years, month-end dates, duplicate
  imports) before the job/endpoint exists.
- **Exit criteria**: Coverage gates hold; a scheduled recurring
  transaction is verified to appear correctly in staging without manual
  intervention.

### Phase 7 — Security Hardening, Performance & Accessibility Audit
- **Goal**: Treat non-functional requirements as first-class, not
  afterthoughts.
- **Scope**: Dependency/secret-scan findings triaged to zero known highs;
  rate limiting tuned; N+1 query audit on all list endpoints (pagination
  enforced everywhere); frontend bundle-size and Lighthouse pass; WCAG AA
  pass on the design system (keyboard nav, contrast, screen-reader
  labels); optional mutation-testing pass on core financial-math modules.
- **TDD approach**: Any bug found here gets a regression test written
  first, reproducing the issue, before the fix.
- **Exit criteria**: No known-high vulnerabilities; Lighthouse
  performance/accessibility scores documented and above agreed
  thresholds; documented pen-test-style checklist (OWASP ASVS-lite)
  completed.

### Phase 8 — Multi-Environment Deployment Maturity & Disaster Recovery
- **Goal**: Production is boring and recoverable.
- **Scope**: Terraform for production finalized and applied; automated
  daily backups with a **tested** restore run; blue/green or rolling
  deploy strategy confirmed with the chosen host; documented rollback
  runbook; alerting wired to a channel (email/Slack) for deploy failures
  and health-check failures.
- **TDD approach**: Infra changes go through `terraform plan` reviewed in
  PR before apply; a restore-from-backup drill is executed and its
  result documented as evidence, not assumed to work.
- **Exit criteria**: A restore drill succeeds against a scratch
  environment; a rollback drill succeeds; runbook exists in `docs/`.

### Phase 9 — QA, UAT, Launch & Post-Launch Operations
- **Goal**: Ship v1 and establish the ongoing maintenance cadence.
- **Scope**: Full regression pass (automated suite + manual UAT against
  the plan's original scope); production tag cut and deployed via the
  approval-gated pipeline; post-launch monitoring window; a lightweight
  backlog for v1.1 (market-priced investments, household/multi-user,
  mobile).
- **TDD approach**: Any UAT-found defect is captured as a failing test
  before being fixed, so the regression suite grows from real usage.
- **Exit criteria**: v1 live in production; monitoring shows a clean
  first week; backlog groomed and prioritized for the next cycle.

## 13. Definition of Done (applies to every PR, every phase)

- Tests written first and passing; coverage gate met.
- Lint and strict type-checking clean (Ruff/mypy, ESLint/tsc).
- CI green on the full matrix, including the Testcontainers-backed
  integration suite.
- OpenAPI schema (and generated TS client) regenerated and committed if
  the API changed.
- No secrets, no commented-out dead code, no unresolved TODO without a
  linked issue.
- Reviewed by at least one other pass (self-review at minimum, with a
  cooling-off re-read before merge, in a solo context).
- Accessibility checked for any UI change (keyboard + screen reader
  smoke pass).

## 14. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Solo-maintainer bus factor | Documentation-as-you-go (ADRs in `docs/adr/`), no undocumented "magic" steps in deploy. |
| Over-engineering for a personal-scale app | Hosting choice (Fly.io/Render) stays lightweight while Docker/Terraform stays portable — rigor without unnecessary infra cost. |
| Exchange-rate accuracy for multi-currency net worth | Always store source + fetch timestamp with a cached rate; never silently substitute a stale or guessed rate without flagging it in the UI. |
| Scope creep across 10 phases | Each phase has a hard exit criteria list; a phase is not extended with "just one more thing" — new ideas go to the Phase 9 backlog. |
| Financial-math bugs (the highest-consequence bug class here) | Worked-example unit tests (Section 8) using real numbers, not just abstract fixtures; mutation testing as a Phase 7 stretch goal specifically on this code. |

## 15. Open Decisions (need a call before Phase 0 finishes)

1. **Hosting provider** for staging/production — Fly.io vs. Render vs.
   AWS from day one. Recommendation: start on Fly.io/Render for cost and
   simplicity; Terraform/Docker keep AWS migration cheap later if needed.
2. **Single-user vs. household** — is shared/multi-user access needed for
   v1, or is this explicitly single-user with household support deferred
   to the backlog?
3. **Investment scope for v1** — fixed-rate/manually-valued instruments
   only (as planned), or is a live market-data feed for stocks/ETFs
   actually needed at launch?
4. **Exchange-rate source** — which rates API/provider to standardize on
   (affects Phase 4 cost and reliability).

## 16. Implementation Status (as of 2026-10-27)

The plan above remains the source of scope. This section records what is now
implemented so a reviewer can see the deltas rather than infer them.

**Backend — complete for Phases 1, 3, 4, 5 and 6**

- Auth, accounts, categories, double-entry transactions, ownership isolation.
- Budgets: half-open calendar months, signed rollover, child-category roll-up.
- Exchange rates: append-only observations, user/global provenance, explicit
  failure on a missing rate, opt-in provider job.
- Investments: fixed-rate accrual and market-priced snapshots, returns, monthly
  compounding, maturity caps.
- Reporting: net worth (cash + holdings, investment accounts as containers),
  month-end history, cash flow, category breakdown, streamed CSV.
- Automation: idempotent recurring rules with a catch-up job; atomic CSV import
  with de-duplication; full JSON export.
- Audit trail for financial mutations, structured API errors and regenerated
  OpenAPI contract. Migrations `0003`–`0007`; ADRs `0007`–`0012`.

**Frontend — Phase 2 plus the feature screens**

- Generated TypeScript API client, memory-only access token with refresh-cookie
  bootstrap, protected routing and an authenticated shell.
- Accessible design-system primitives (labels/errors, dialog focus handling,
  alerts, progress, pagination, chart data tables).
- Screens for dashboard, accounts, categories, transactions/transfers/import,
  budgets, investments/valuations, reports, recurring rules and settings/export.
- Vitest/RTL coverage across every screen, plus Playwright critical journeys.
  ADRs `0013`–`0016`.

**Still open**

- Phase 7 hardening: auth rate limiting, N+1 audit, Lighthouse/bundle checks,
  full WCAG AA pass, dependency/secret scan triage.
- Phase 8–9: production Terraform, backup restore drill, UAT and launch.
- Open Decisions in Section 15 (hosting, household sharing, live market data,
  FX provider) still need a product decision.
