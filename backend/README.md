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

- PostgreSQL: `localhost:5432`
- pgAdmin: `http://localhost:5050`

## Environment

Copy `.env.example` to `.env` and adjust values if needed.

```bash
cp .env.example .env
```

## Migrations

```bash
alembic -c backend/alembic.ini upgrade head
```

## Run API

```bash
uvicorn backend.app.main:app --reload
```

Health:

```bash
curl http://localhost:8000/health
```

Generate:

```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"domain":"logistics","load_type":"bulk","format":"csv","records":1000}'
```

Validate:

```bash
curl -X POST http://localhost:8000/api/v1/validate \
  -H "Content-Type: application/json" \
  -d '{"run_id":"<run-id>"}'
```

Analytics:

```bash
curl http://localhost:8000/api/v1/admin/analytics/overview
```

Quality analytics:

```bash
curl http://localhost:8000/api/v1/admin/analytics/quality/domains
curl http://localhost:8000/api/v1/admin/analytics/quality/load-types
curl http://localhost:8000/api/v1/admin/analytics/quality/trends
curl http://localhost:8000/api/v1/admin/analytics/quality/lowest-runs
curl http://localhost:8000/api/v1/admin/analytics/quality/highest-runs
```

## Scope

Implemented in this phase:

- FastAPI application factory
- `/health`
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
