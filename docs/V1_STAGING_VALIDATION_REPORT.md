# DataForge V1 Staging Validation Report

Date: 2026-08-08  
Decision: READY FOR LIMITED BETA

## Scope

V1 feature development is frozen. This pass validated the current V1 app only:

- Scenario Library
- Scenario Builder
- multi-failure injection configuration
- required-table visibility
- saved scenario templates
- run history
- rerun / comparison surfaces
- ground truth export
- benchmarking
- detector evaluation
- precision / recall / F1
- benchmark PASS / FAIL
- async benchmark generation
- detector JSON / JSONL / CSV submission
- detector file upload
- benchmark cancellation
- benchmark artifact manifest
- quota / concurrency behavior

No Phase 2 features were added.

## Staging stack validated

- PostgreSQL: Docker `postgres:16`
- Database: `dataforge_v1_staging`
- Port: `55435 -> 5432`
- Backend: FastAPI on `http://127.0.0.1:8020`
- Frontend: Next.js production server on `http://127.0.0.1:3001`
- API key: staging-only `v1-staging-key`
- Frontend API base: `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8020`
- Stream query tokens: disabled in staging config
- Benchmark concurrency: `BENCHMARK_CONCURRENT_RUNS=2`
- Detector upload max: `BENCHMARK_DETECTOR_UPLOAD_MAX_BYTES=5000000`

Alembic migration status:

```text
0009_benchmark_runs (head)
```

## Commands used

```bash
docker run -d \
  --name dataforge-postgres-v1-staging \
  -e POSTGRES_DB=dataforge_v1_staging \
  -e POSTGRES_USER=dataforge \
  -e POSTGRES_PASSWORD=dataforge123 \
  -p 55435:5432 \
  postgres:16

DATABASE_URL='postgresql+psycopg://dataforge:dataforge123@127.0.0.1:55435/dataforge_v1_staging' \
  /opt/anaconda3/bin/python3.12 -m alembic -c backend/alembic.ini upgrade head

APP_ENV=staging \
DATAFORGE_API_KEY=v1-staging-key \
DATABASE_URL='postgresql+psycopg://dataforge:dataforge123@127.0.0.1:55435/dataforge_v1_staging' \
OUTPUT_DIR='/private/tmp/dataforge-v1-staging-output' \
CORS_ORIGINS='http://127.0.0.1:3001' \
STREAM_QUERY_TOKEN_ENABLED=false \
RATE_LIMIT_ENABLED=false \
BENCHMARK_CONCURRENT_RUNS=2 \
BENCHMARK_DETECTOR_UPLOAD_MAX_BYTES=5000000 \
  /opt/anaconda3/bin/python3.12 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8020

cd frontend
NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8020' \
NEXT_PUBLIC_ENABLE_DEMO_API_KEY=true \
NEXT_PUBLIC_DATAFORGE_API_KEY='v1-staging-key' \
  npm run build

NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8020' \
NEXT_PUBLIC_ENABLE_DEMO_API_KEY=true \
NEXT_PUBLIC_DATAFORGE_API_KEY='v1-staging-key' \
  npm run start -- --hostname 127.0.0.1 --port 3001
```

Playwright validation harness:

```bash
FRONTEND_URL='http://127.0.0.1:3001' \
BACKEND_URL='http://127.0.0.1:8020' \
DATAFORGE_API_KEY='v1-staging-key' \
  node /private/tmp/dataforge-v1-playwright-audit/v1-staging-validation.js
```

## Automated validation results

Backend regression:

```text
378 passed, 3 skipped in 53.55s
```

Frontend:

```text
npm run typecheck: PASS
npm run build: PASS
```

Browser/live E2E:

```text
72 checks passed
0 failed
```

Dependency audit:

```text
npm audit --omit=dev --audit-level=moderate: found 0 vulnerabilities
python -m pip_audit . --strict: No known vulnerabilities found
```

Source-map exposure:

```text
frontend/.next/static public source maps: none found
server-only .map files exist under frontend/.next/server
```

## Live flows verified

Passed:

- backend health
- frontend production server health
- backend security headers
- frontend security headers
- exact CORS rejection for untrusted origin
- protected API endpoints reject missing API key
- protected API endpoints reject invalid API key
- Scenario Builder loads executable V1-ready scenarios
- scenario configuration loads
- required tables display
- failure configuration displays
- generation plan preview displays
- saved template create/load flow
- scenario dataset generation
- async job polling
- generated run retrieval
- ground-truth evidence display
- benchmark definition creation
- fresh benchmark launch
- waiting-for-detector lifecycle
- detector JSON submission
- benchmark PASS/FAIL evaluation
- Run History page loading
- ground truth export: JSON, JSONL, CSV
- dataset manifest export
- benchmark artifact manifest export
- dataset ZIP download
- generated file download
- download headers do not leak local filesystem paths
- detector upload: valid JSON
- detector upload: valid JSONL
- detector upload: valid CSV
- invalid upload extension rejection
- path-like upload filename rejection
- malformed JSON/JSONL/CSV clean rejection
- oversized detector upload rejection
- 1K benchmark performance smoke
- 10K benchmark performance smoke
- responsive smoke at 375, 768, 1440, and 1920 widths
- axe critical/serious accessibility gate for Scenario Builder
- axe critical/serious accessibility gate for Run History

## Bugs found and fixed

### High: benchmark waiting-for-detector runs could not be cancelled

Finding:

- Benchmark runs in `waiting_for_detector` counted against practical lifecycle usage, but the cancel endpoint rejected them with 409.
- This could strand beta users if they launch a benchmark and never submit detector output.

Fix:

- Updated `POST /api/v1/benchmark-runs/{benchmark_run_id}/cancel` to allow cancellation from:
  - `waiting_for_detector`
  - `evaluation_failed`
- Added an accurate cancellation reason for post-generation cancellation.
- Added regression test: `test_waiting_for_detector_benchmark_run_can_be_cancelled`.

### High: detector upload malformed payloads needed cleaner rejection

Finding:

- Malformed detector JSON/JSONL/CSV could surface parser-level failures instead of a stable user-facing validation error.

Fix:

- Hardened detector payload parsing to return clean `400 INVALID_DETECTOR_OUTPUT`.
- Added validation normalization before accepting detector submissions.

### High: frontend production security headers missing

Finding:

- Frontend production pages needed explicit security headers.

Fix:

- Added Next.js headers:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: no-referrer`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=()`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`

### High: accessibility critical/serious findings

Finding:

- Scenario Builder had axe-critical unlabeled controls.
- Run History had axe-serious success badge contrast issues.

Fix:

- Added accessible labels to:
  - saved-template delete icon buttons
  - benchmark run selection controls
  - comparison run selection controls
  - detector name input
  - detector JSON textarea
- Darkened the success color token for badge contrast.

Final axe status:

- Scenario Builder: 0 critical, 0 serious
- Run History: 0 critical, 0 serious

## Remaining findings

### Medium

- Scenario Builder has moderate landmark findings:
  - nested / duplicate main landmark
  - missing page-level h1
- Run History has moderate heading/landmark findings.

These do not block limited beta but should be cleaned up during UI polish.

### Medium

- Background execution remains process-local.
- This is acceptable for controlled limited beta, but not durable enterprise execution.
- If the process restarts mid-job, in-flight background tasks may not resume automatically.

### Medium

- Demo API key in browser is acceptable only for internal/staging/demo mode.
- Public beta should use real user authentication and per-user ownership checks.

### Medium

- In-memory rate limiting is single-instance only.
- Multi-instance deployments should move limits to Redis/Upstash/edge middleware.

### Medium

- The validation harness observed one benign browser console 404 for a missing resource, likely favicon/static noise.
- No page errors, request failures, or unexpected API/browser 4xx/5xx were observed during app flows.

## Security posture

Passed:

- CORS rejects untrusted origins.
- Missing and invalid API keys are rejected on protected APIs.
- Detector upload rejects suspicious extensions and path-like filenames.
- Malformed detector payloads fail cleanly.
- Oversized detector upload is rejected.
- Download responses do not leak local filesystem paths.
- Browser storage did not contain secrets in localStorage/sessionStorage/cookies during the audited flow.
- Public static source maps were not emitted.
- npm and Python dependency audits found no known vulnerabilities.

Limited-beta restrictions:

- Keep invite-only access.
- Use exact production CORS origins.
- Keep demo API key disabled for real users.
- Do not expose admin routes publicly without real auth/ownership.
- Treat process-local background execution as a known V1 limitation.

## Files changed in this validation pass

- `backend/app/api/v1/routes.py`
- `backend/tests/test_benchmarking_api.py`
- `frontend/next.config.ts`
- `frontend/components/scenarios/saved-scenario-templates.tsx`
- `frontend/components/scenarios/benchmarking-panel.tsx`
- `frontend/app/globals.css`

## Final V1 gate

Critical findings open: 0  
High findings open: 0  
Backend regression suite: PASS  
Frontend typecheck: PASS  
Frontend production build: PASS  
Critical browser flows: PASS  
Security headers: PASS  
CORS: PASS  
Upload/download security: PASS  
Fresh migration: PASS  
Accessibility critical/serious: 0  

Decision: READY FOR LIMITED BETA
