# DataForge Backend Foundation

Phase 1 backend foundation for DataForge. This wraps the existing domain
generation engine with FastAPI, SQLAlchemy persistence, Alembic migrations,
Dockerized PostgreSQL, and admin analytics APIs.

## Run infrastructure

From the repository root:

```bash
docker compose up -d
```

Services:

- PostgreSQL: `127.0.0.1:55434`
- pgAdmin: `http://localhost:5051`

## Environment

Copy `.env.example` to `.env` and adjust values if needed.

```bash
cp .env.example .env
```

The default local database URL is:

```bash
DATABASE_URL=postgresql+psycopg://dataforge:dataforge123@127.0.0.1:55434/dataforge
```

If you see `password authentication failed for user "dataforge"`, the
PostgreSQL server or Docker volume on the configured port was probably
initialized with a different password. For a disposable local development
database, reset it with:

```bash
docker compose down -v
docker compose up -d postgres
alembic -c backend/alembic.ini upgrade head
```

Do not use `docker compose down -v` if the local PostgreSQL volume contains data
you need to keep.

## Migrations

```bash
alembic -c backend/alembic.ini upgrade head
```

## Run API

```bash
uvicorn backend.app.main:app --reload --port 8010
```

Health:

```bash
curl http://127.0.0.1:8010/health
```

Catalog tables:

```bash
curl http://127.0.0.1:8010/api/v1/catalog/tables/retail
```

Generate:

```bash
curl -X POST http://127.0.0.1:8010/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"domain":"logistics","load_type":"bulk","format":"csv","records":1000}'
```

Validate:

```bash
curl -X POST http://127.0.0.1:8010/api/v1/validate \
  -H "Content-Type: application/json" \
  -d '{"run_id":"<run-id>"}'
```

Analytics:

```bash
curl http://127.0.0.1:8010/api/v1/admin/analytics/overview
```

Quality analytics:

```bash
curl http://127.0.0.1:8010/api/v1/admin/analytics/quality/domains
curl http://127.0.0.1:8010/api/v1/admin/analytics/quality/load-types
curl http://127.0.0.1:8010/api/v1/admin/analytics/quality/trends
curl http://127.0.0.1:8010/api/v1/admin/analytics/quality/lowest-runs
curl http://127.0.0.1:8010/api/v1/admin/analytics/quality/highest-runs
```

## Scope

Implemented in this phase:

- FastAPI application factory
- `/health`
- `/api/v1/catalog/tables/{domain}`
- `/api/v1/generate`
- `/api/v1/validate`
- `/api/v1/runs`
- `/api/v1/runs/{run_id}`
- `/api/v1/admin/analytics/*`
- SQLAlchemy 2.0 models
- Repository layer
- Alembic migration
- Structured JSON logging
- Centralized error handling
- Docker Compose for PostgreSQL and pgAdmin
- Standard validation report contract
- Quality-score persistence and analytics

Not implemented in this phase:

- UI
- streaming APIs
- projects
- scenarios
- test packages
