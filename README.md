# Personal Finance & Investment Tracker

Expense management, budgeting and multi-currency investment tracking.

Full engineering plan: [`PLAN.md`](./PLAN.md). Architecture decisions:
[`docs/adr/`](./docs/adr/).

**Current status: backend feature phases and the frontend are implemented** —
Phase 1 (auth, accounts & ledger), Phase 3 (budgets), Phase 4 (investments &
exchange rates), Phase 5 (reporting), Phase 6 (recurring transactions,
import/export), and the Phase 2 frontend shell plus screens for every backend
feature. Phase 7 security/performance hardening remains.

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.12, SQLAlchemy 2 (async), Alembic, Pydantic v2 |
| Database | PostgreSQL 16 |
| Frontend | React 19, TypeScript (strict), Vite 7, TanStack Query, Tailwind |
| Testing | pytest + Testcontainers, Vitest + RTL, Playwright |
| Tooling | uv, Ruff, mypy --strict, ESLint, Prettier, yarn |
| Infra | Docker, docker-compose, Terraform, GitHub Actions |

## Prerequisites

- Docker (required — Testcontainers runs a real Postgres for integration tests)
- [uv](https://docs.astral.sh/uv/), Node 22+, yarn 1.x

## Quick start (containerized, closest to production)

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up --build
```

- App: http://localhost:8080
- API: http://localhost:8000 (docs at `/docs`)

Host ports collide easily; override them without editing the compose file:

```bash
DB_HOST_PORT=55432 BACKEND_HOST_PORT=8010 FRONTEND_HOST_PORT=8090 \
  docker compose -f infra/docker-compose.yml up --build
```

## Local development

### Backend

```bash
cd backend
uv sync                     # install dependencies from the lockfile
uv run python -m app.db.migrate   # apply migrations
uv run uvicorn app.main:app --reload
```

Requires `DATABASE_URL` and `SECRET_KEY` in the environment (see `.env.example`).
The app refuses to start if required config is missing or malformed.

### Frontend

CORS: in `APP_ENV=local` the API defaults to the Vite dev/preview origins on
`localhost` and `127.0.0.1` (ports 5173 and 4173). Set `CORS_ORIGINS` explicitly
if you use another host/port. Staging and production never receive defaults.

```bash
cd frontend
yarn install
yarn generate:api           # refresh typed client from backend/openapi.json
yarn dev                    # http://localhost:5173 (uses .env.development)
```

The SPA boots by exchanging the httpOnly refresh cookie for an access token,
then renders protected routes. Access tokens are memory-only (ADR 0013); API
types are generated from OpenAPI (ADR 0014); money is parsed and formatted
without float arithmetic (ADR 0015).

Screens:

| Route | Purpose |
|---|---|
| `/login`, `/register` | Sign in / create an account |
| `/` | Dashboard: net worth, budget health, recent transactions |
| `/transactions` | Filterable ledger, add/edit, transfers, CSV import |
| `/budgets` | Monthly budget-vs-actual with rollover |
| `/investments` | Holdings, returns, valuation snapshots |
| `/reports` | Net worth history, cash flow, category breakdown, CSV download |
| `/recurring` | Rule CRUD, pause/resume, run-now |
| `/accounts`, `/categories` | Ledger containers and classification |
| `/settings` | Profile, manual FX rates, full JSON export |

## Testing

The project is developed test-first (plan Section 8). Write the failing test
before the production code.

```bash
# Backend: unit + integration (real Postgres), 90% coverage gate
cd backend && uv run pytest

# Frontend: unit/component, 85% coverage gate
cd frontend && yarn test:coverage

# E2E: build first, then drive a real browser against a running stack
cd frontend && VITE_API_BASE_URL=http://localhost:8000 yarn build && yarn test:e2e

# E2E against an already-running stack or a deployed environment
E2E_BASE_URL=http://localhost:8090 yarn test:e2e
```

If the Docker CLI is configured with a credential helper that is unavailable
non-interactively (common on macOS CI agents), point Testcontainers at the
daemon directly:

```bash
DOCKER_HOST=unix://$HOME/.docker/run/docker.sock DOCKER_CONFIG=/tmp/docker-config \
  uv run pytest
```

## Quality gates

Every gate below runs in CI on each PR and must pass before merge.

```bash
cd backend  && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
cd frontend && yarn lint && yarn format:check && yarn typecheck && yarn test:coverage && yarn build
```

Current gates: backend 486 tests at 94.51% coverage; frontend 214 tests at
98.08% statements / 85.15% branches / 90.86% functions, with the 85% gate
enforced by Vitest.

## API

The OpenAPI schema is committed at `backend/openapi.json` and is the contract
the frontend generates its client from. CI fails if it drifts from the code.

```bash
cd backend && uv run python scripts/export_openapi.py   # after any API change
```

| Area | Endpoints |
|---|---|
| Auth | `POST /api/v1/auth/{register,login,refresh,logout}`, `GET /api/v1/auth/me` |
| Accounts | `GET, POST /api/v1/accounts`, `GET, PATCH, DELETE /api/v1/accounts/{id}`, `GET /api/v1/accounts/{id}/balance` |
| Categories | `GET, POST /api/v1/categories`, `GET, PATCH, DELETE /api/v1/categories/{id}` |
| Transactions | `GET, POST /api/v1/transactions`, `GET, PATCH, DELETE /api/v1/transactions/{id}`, `POST /api/v1/transactions/transfers`, `POST /api/v1/transactions/import` |
| Budgets | `GET, POST /api/v1/budgets`, `GET, PATCH, DELETE /api/v1/budgets/{id}`, `GET /api/v1/budgets/{id}/status`, `GET /api/v1/budgets/status` |
| Exchange rates | `GET, POST /api/v1/exchange-rates`, `GET /api/v1/exchange-rates/latest`, `GET /api/v1/exchange-rates/convert` |
| Investments | `GET, POST /api/v1/investments`, `GET, PATCH, DELETE /api/v1/investments/{id}`, `GET /api/v1/investments/{id}/returns`, `GET, POST /api/v1/investments/{id}/valuations`, `DELETE /api/v1/investments/{id}/valuations/{valuation_id}` |
| Reports | `GET /api/v1/reports/net-worth`, `GET /api/v1/reports/net-worth/history`, `GET /api/v1/reports/cash-flow`, `GET /api/v1/reports/category-breakdown`, `GET /api/v1/reports/transactions.csv` |
| Recurring rules | `GET, POST /api/v1/recurring-rules`, `GET, PATCH, DELETE /api/v1/recurring-rules/{id}`, `POST /api/v1/recurring-rules/{id}/run` |
| Export | `GET /api/v1/export` |

Key domain rules (see `docs/adr/`):

- **Money** is stored as integer minor units with an explicit currency; amounts
  too precise for their currency are rejected, never rounded (ADR 0004).
- **Refresh tokens** are httpOnly cookies, stored hashed, and rotate on every
  use; replaying a rotated token fails (ADR 0005).
- **Transfers** are two linked legs sharing a `transfer_group_id` that always
  net to zero; deleting one deletes both (ADR 0006).
- **Budgets** use half-open calendar months, roll unspent/overspent allowance
  forward when enabled, and roll child-category spend into the parent (ADR 0007).
- **Exchange rates** are append-only observations with source and timestamp.
  Conversions never guess: a missing rate is a 422 naming the pair and date
  (ADR 0008).
- **Fixed-rate investments** accrue by calendar month (24% p.a. on ₦10m is
  exactly ₦200k/month) and stop at maturity; snapshots override accrual and
  report their source (ADR 0009).
- **Investment accounts are containers** for holdings; their ledger balances are
  not added to net worth alongside the holdings, which avoids double counting a
  funded purchase (ADR 0012).
- **Recurring rules** are idempotent per `(rule, occurrence)` and preserve the
  intended day-of-month across short months (ADR 0010).
- **CSV import** validates the entire file before writing and de-duplicates by
  bank reference or stable row hash (ADR 0011).
- **Ownership** is enforced on every query — another user's resource returns
  404, so existence never leaks.
- **Audit log** records every financial mutation in the same transaction as the
  change, with the request correlation ID.

## Scheduled jobs

Both are safe to run repeatedly and are designed for a daily scheduler.

```bash
cd backend
uv run python -m app.jobs.fetch_exchange_rates   # fetch provider rates (opt-in)
uv run python -m app.jobs.run_recurring          # materialise due occurrences
```

The FX job is opt-in: without `EXCHANGE_RATE_API_URL` it logs a skip and exits
0. A provider failure exits non-zero and leaves existing rates untouched. The
provider contract is a JSON object of the form
`{"base": "GBP", "date": "2026-10-27", "rates": {"USD": 1.27}}`; the key is
sent in a header, never the URL.

## Database migrations

Migrations are the only way the schema changes — never `create_all`.

```bash
cd backend
uv run alembic revision --autogenerate -m "add transactions table"
uv run alembic upgrade head        # or: uv run python -m app.db.migrate
uv run alembic downgrade -1
```

## Deployment

- **Staging** — automatic on merge to `main` (`deploy-staging.yml`): build and
  push images to GHCR, `terraform apply`, run migrations, Playwright smoke suite.
- **Production** — triggered by a `v*.*.*` tag (`deploy-production.yml`), gated
  on manual approval. Images are **promoted** from staging, never rebuilt.
- **Rollback** — re-run the production workflow with the previous image tag
  (recorded in each deploy's job summary).

### Required GitHub configuration

Environment secrets — `staging` and `production`:

| Secret | Purpose |
|---|---|
| `FLY_API_TOKEN` | Terraform provider auth |
| `<ENV>_DATABASE_URL` | Postgres DSN for the environment |
| `<ENV>_SECRET_KEY` | JWT signing key |

Environment variables: `STAGING_API_URL`, `STAGING_APP_URL`,
`PRODUCTION_API_URL`, `PRODUCTION_APP_URL`, `PRODUCTION_CURRENT_TAG`.

Terraform state uses an S3-compatible backend; copy
`infra/terraform/<env>/backend.hcl.example` to `backend.hcl` and run
`terraform init -backend-config=backend.hcl`.

## Configuration

All backend config is environment-variable driven and validated at startup.

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | yes | `postgresql+asyncpg://…` DSN |
| `SECRET_KEY` | yes | JWT signing key (16+ chars) |
| `CORS_ORIGINS` | no | Comma-separated allowed origins; no `*` in staging/prod |
| `EXCHANGE_RATE_API_URL` | no | Enables the scheduled rates job |
| `EXCHANGE_RATE_API_KEY` | no | Sent in `EXCHANGE_RATE_API_KEY_HEADER` |
| `EXCHANGE_RATE_API_KEY_HEADER` | no | Defaults to `apikey` |
| `EXCHANGE_RATE_BASE_CURRENCY` | no | Defaults to `GBP` |
| `EXCHANGE_RATE_QUOTES` | no | Comma-separated, defaults to `USD,EUR,NGN` |

## Repository layout

```
backend/    FastAPI app, migrations, jobs, tests
frontend/   React SPA, generated API client, component tests, Playwright specs
infra/      docker-compose (local) + Terraform (staging, production)
docs/adr/   architecture decision records
.github/    CI and deploy workflows
```
