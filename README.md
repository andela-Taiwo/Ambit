# Personal Finance & Investment Tracker

Expense management, budgeting and multi-currency investment tracking.

Full engineering plan: [`PLAM.md`](./PLAM.md). Architecture decisions:
[`docs/adr/`](./docs/adr/).

**Current phase: Phase 0 — foundations, environments & CI/CD skeleton (complete).**

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

```bash
cd frontend
yarn install
yarn dev                    # http://localhost:5173
```

## Testing

The project is developed test-first (plan Section 8). Write the failing test
before the production code.

```bash
# Backend: unit + integration (real Postgres), 90% coverage gate
cd backend && uv run pytest

# Frontend: unit/component, 85% coverage gate
cd frontend && yarn test:coverage

# E2E: builds the app and drives a real browser
cd frontend && yarn test:e2e

# E2E against an already-running stack or a deployed environment
E2E_BASE_URL=http://localhost:8090 yarn test:e2e
```

## Quality gates

Every gate below runs in CI on each PR and must pass before merge.

```bash
cd backend  && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
cd frontend && yarn lint && yarn format:check && yarn typecheck && yarn test:coverage && yarn build
```

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

## Repository layout

```
backend/    FastAPI app, migrations, tests
frontend/   React SPA, component tests, Playwright specs
infra/      docker-compose (local) + Terraform (staging, production)
docs/adr/   architecture decision records
.github/    CI and deploy workflows
```
