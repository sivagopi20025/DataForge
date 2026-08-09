# DataForge Deployment Readiness

This document captures the current deployment contract without adding new
product features.

## Runtime services

Recommended local/dev ports:

| Service | URL |
|---|---|
| PostgreSQL container | `127.0.0.1:55434` |
| FastAPI backend | `127.0.0.1:8010` |
| Next.js frontend | `127.0.0.1:3000` |
| pgAdmin | `127.0.0.1:5051` |

## Required environment

Backend:

```bash
APP_ENV=production
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<db>
DATAFORGE_API_KEY=<long-random-secret>
OUTPUT_DIR=/var/lib/dataforge/output
MAX_BATCH_RECORDS=500000
CORS_ORIGINS=https://<frontend-domain>
GENERATED_FILE_RETENTION_DAYS=7
STORAGE_BACKEND=local
OBJECT_STORAGE_BUCKET=
OBJECT_STORAGE_BASE_URL=
OBJECT_STORAGE_ENDPOINT_URL=
OBJECT_STORAGE_REGION=us-east-1
OBJECT_STORAGE_ACCESS_KEY_ID=
OBJECT_STORAGE_SECRET_ACCESS_KEY=
OBJECT_STORAGE_PRESIGN_SECONDS=300
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=120
RATE_LIMIT_WINDOW_SECONDS=60
STREAM_QUERY_TOKEN_ENABLED=false
WEBHOOK_ALLOWED_DOMAINS=hooks.example.com
```

Frontend:

```bash
NEXT_PUBLIC_API_BASE_URL=https://<backend-domain>
# Internal/demo deployments only; public browser env vars are visible.
NEXT_PUBLIC_ENABLE_DEMO_API_KEY=false
NEXT_PUBLIC_DATAFORGE_API_KEY=
```

## Authentication foundation

If `DATAFORGE_API_KEY` is empty, API-key enforcement is disabled for local
development. If it is set, protected endpoints require:

```http
X-API-Key: <DATAFORGE_API_KEY>
```

Protected endpoint groups:

- generation
- generation jobs/status
- validation
- run history
- file downloads
- admin analytics

This is a foundation only. Before public beta, replace or augment this with
user/session-based auth if multiple users need separate access control.
For an internal demo UI, set `NEXT_PUBLIC_ENABLE_DEMO_API_KEY=true` and
`NEXT_PUBLIC_DATAFORGE_API_KEY=<demo-key>` to send the header from the browser.
Do not enable this for public users. Public browser-exposed keys are not real
authorization. For beta/public multi-user access, place Supabase/Auth.js/Clerk
or another identity provider in front of the backend and validate user sessions
server-side before allowing run history, downloads, admin APIs, or stream access.

## Rate limiting

Protected endpoints are guarded by a lightweight in-memory fixed-window rate
limiter. It is configured with:

| Variable | Default | Meaning |
|---|---:|---|
| `RATE_LIMIT_ENABLED` | `true` | Enables/disables protected endpoint rate limiting |
| `RATE_LIMIT_REQUESTS` | `120` | Max requests per identity/path/window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Window size in seconds |

When exceeded, the backend returns:

```json
{
  "error": "Rate limit exceeded",
  "code": "RATE_LIMIT_EXCEEDED",
  "retry_after_seconds": 42
}
```

The response status is `429` and includes the `Retry-After` header.

Production note: this limiter is process-local. It is enough for a single
backend instance. Multi-instance deployments should move the same policy to a
shared store such as Redis or to the platform edge/proxy.

## Streaming token and webhook security

Use stream tokens only in headers:

```http
Authorization: Bearer <stream_token>
```

In production set:

```bash
STREAM_QUERY_TOKEN_ENABLED=false
```

Query-string stream tokens are rejected automatically when `APP_ENV=production`.

Webhook push mode is protected by these rules:

- `webhook_url` must use `https://`.
- localhost, private IP ranges, link-local IPs, reserved IPs, and cloud metadata
  IPs are blocked.
- production requires `WEBHOOK_ALLOWED_DOMAINS`.
- webhook redirects are not followed automatically.
- webhook secrets are not persisted in plaintext; they are held only in memory
  long enough for the current background stream task, while the database keeps
  only a hash.

## Batch generation resource guard

`MAX_BATCH_RECORDS` protects the backend from accidental or abusive large batch
requests. The default is `500000`, matching the current UI limit. Requests above
this value are rejected before a background job is queued.

Raise this only after moving generation to stronger worker/runtime capacity and
verifying memory, disk, and object-storage throughput for the larger target.

## Async/background generation strategy

Current generation uses FastAPI `BackgroundTasks` and a `generation_jobs` table.
`POST /api/v1/generate` returns immediately:

```json
{
  "job_id": "<job-id>",
  "status": "queued",
  "run_id": null
}
```

Clients poll `GET /api/v1/jobs/{job_id}`. Job states are:

- `queued`
- `running`
- `completed`
- `failed`

Completed jobs include `run_id`, generated file metadata, and validation
results. Failed jobs persist `error_message` for API/UI display.

This keeps generation logic inside `DatasetGenerationService`; background jobs
only orchestrate status transitions and persistence.

Production note: FastAPI background tasks are intentionally lightweight. For
multi-worker or crash-resilient deployments, move the same job contract to Redis
+ RQ/Celery/Arq without changing domain generation logic.

## Object storage strategy

Generated-file downloads now go through a storage service. Local filesystem is
the default backend and remains fully supported.

Deployment options:

| Stage | Strategy |
|---|---|
| Local/dev | local `OUTPUT_DIR` |
| Single VM | mounted persistent volume |
| Multi-instance/beta | S3-compatible bucket or Supabase Storage S3 API |

Generated file metadata stores:

- `storage_backend`
- `object_key`
- `file_path`
- `size_bytes`
- `content_type`

### Local storage

```bash
STORAGE_BACKEND=local
OUTPUT_DIR=/var/lib/dataforge/output
```

The download endpoint validates object keys and paths stay inside `OUTPUT_DIR`.

### S3-compatible storage

Use this for AWS S3, MinIO, Cloudflare R2, Supabase S3 compatibility, or any
S3-compatible provider:

```bash
STORAGE_BACKEND=s3-compatible
OBJECT_STORAGE_BUCKET=<bucket-name>
OBJECT_STORAGE_ENDPOINT_URL=<provider-s3-endpoint-or-empty-for-aws>
OBJECT_STORAGE_REGION=us-east-1
OBJECT_STORAGE_ACCESS_KEY_ID=<access-key>
OBJECT_STORAGE_SECRET_ACCESS_KEY=<secret-key>
OBJECT_STORAGE_BASE_URL=<optional-public-base-url>
OBJECT_STORAGE_PRESIGN_SECONDS=300
```

Downloads for S3-compatible storage return a short-lived presigned redirect.
For Supabase, use the S3 compatibility endpoint and credentials from the
Supabase project storage settings.

Recommended future abstraction:

- local file streaming for local storage
- presigned URLs for object storage
- lifecycle policies in the bucket for retention

Avoid relying on browser-facing absolute server paths long term; use
`object_key` as the durable storage reference.

## File cleanup and retention

Local generated run directories can be cleaned with:

```bash
python -m backend.app.services.retention --retention-days 7
python -m backend.app.services.retention --retention-days 7 --apply
```

Storage-aware cleanup deletes generated objects through the configured storage
backend using `generated_files.object_key`:

```bash
python -m backend.app.services.retention --storage-aware --retention-days 7
python -m backend.app.services.retention --storage-aware --retention-days 7 --apply
```

Run the dry-run command first. In deployment, schedule the `--apply` command via
cron, Kubernetes CronJob, or platform scheduler.

This deletes generated objects only. Database row archival/deletion should be
designed once user-facing retention semantics are finalized.

## Backend Docker deployment

Build the production backend image from the repository root:

```bash
docker build -f backend/Dockerfile -t dataforge-backend:0.6.0 .
```

Run locally against the Docker Compose PostgreSQL service:

```bash
docker compose up -d postgres
alembic -c backend/alembic.ini upgrade head
docker run --rm -p 8010:8000 \
  --env-file .env \
  dataforge-backend:0.6.0
```

Health check:

```bash
curl http://127.0.0.1:8010/health
```

Run migrations before starting a production container:

```bash
alembic -c backend/alembic.ini upgrade head
```

If your platform supports release commands, use the migration command as the
release/prestart step.

## Render deployment example

A Render blueprint is provided at:

```text
deploy/render.yaml
```

Recommended flow:

1. Push the repository to GitHub.
2. In Render, choose **New +** → **Blueprint**.
3. Select the repository.
4. Use `deploy/render.yaml`.
5. Replace `CORS_ORIGINS` with the real frontend URL.
6. Keep `DATAFORGE_API_KEY` secret and copy it into the frontend environment
   only for internal/demo deployments.
7. Run Alembic migrations after the database is created:

```bash
alembic -c backend/alembic.ini upgrade head
```

Render uses:

- Docker context: repository root
- Dockerfile: `backend/Dockerfile`
- Health check: `/health`
- PostgreSQL: managed Render Postgres from the blueprint

## Vercel frontend deployment example

Recommended flow:

1. Push the repository to GitHub.
2. In Vercel, import the repository.
3. Set the project root directory to:

```text
frontend
```

4. Use the default Next.js build settings:

```bash
npm install
npm run build
```

5. Configure environment variables:

```bash
NEXT_PUBLIC_API_BASE_URL=https://<render-backend-domain>
NEXT_PUBLIC_DATAFORGE_API_KEY=<demo-api-key-if-needed>
```

6. In the backend environment, set:

```bash
CORS_ORIGINS=https://<vercel-frontend-domain>
```

For a private/internal demo, the browser-exposed API key is acceptable. For
public users, replace this with user-scoped authentication before launch.

## Final demo deployment checklist

Before a live demo:

- Backend service is deployed and `/health` returns `200`.
- PostgreSQL database exists and migrations are applied:

```bash
alembic -c backend/alembic.ini upgrade head
```

- `DATAFORGE_API_KEY` is set on backend.
- Frontend `NEXT_PUBLIC_API_BASE_URL` points to the backend URL.
- Frontend `NEXT_PUBLIC_DATAFORGE_API_KEY` matches backend key for internal demo.
- Backend `CORS_ORIGINS` includes the Vercel frontend URL.
- `RATE_LIMIT_ENABLED=true` with demo-safe limits.
- `STORAGE_BACKEND` is `local` for single-instance demo or `s3-compatible` for
  persistent/multi-instance demo.
- If using object storage, bucket credentials and presigned downloads are tested.
- Storage-aware retention dry-run succeeds:

```bash
python -m backend.app.services.retention --storage-aware --retention-days 7
```

- UI smoke flow passes:
  - open generator
  - generate dataset
  - job completes
  - run detail loads
  - validation results display
  - run history/admin history updates
  - generated file downloads

## CI

GitHub Actions runs:

- Python install with Parquet extras
- all backend/domain/API tests
- Alembic upgrade/downgrade/upgrade
- frontend `npm ci`
- `npm audit --audit-level=moderate`
- frontend typecheck
- frontend production build

## Production blockers remaining

- Background generation is process-local; it is not yet crash-resilient or
  multi-worker durable.
- API-key auth is coarse-grained, not user-scoped.
- Local file storage needs object storage for multi-instance deployment.
- Object storage is implemented, but production bucket lifecycle/retention still
  needs to be configured in the provider.
- Rate limiting is process-local; use Redis or edge limits for multi-instance
  deployments.
- Retention cleanup needs a scheduled job in the target platform.
