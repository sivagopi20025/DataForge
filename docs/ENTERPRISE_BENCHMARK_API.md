# DataForge Enterprise Benchmark API

Batch 13 turns a benchmark definition into an executable, reproducible test specification.

The enterprise workflow is:

1. Discover or create a benchmark definition.
2. Launch a benchmark run.
3. Poll benchmark run status.
4. Download generated dataset artifacts and ground truth.
5. Run your external detector.
6. Submit detector output.
7. Read PASS / FAIL metrics and evidence.

All protected examples assume:

```bash
export DATAFORGE_API=http://127.0.0.1:8010
export DATAFORGE_API_KEY=your-api-key
```

## 1. Create a benchmark definition

```bash
curl -s -X POST "$DATAFORGE_API/api/v1/benchmarks" \
  -H "X-API-Key: $DATAFORGE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Payment Retry Detector Benchmark",
    "domain": "ecommerce",
    "scenario_id": "ecommerce_payment_retry",
    "records": 1000,
    "output_format": "csv",
    "seed": 42,
    "failure_plan": {
      "scenario_id": "ecommerce_payment_retry",
      "seed": 42,
      "overlap_mode": "allow_overlap",
      "failures": [
        {
          "primitive_id": "duplicate_payment_retry",
          "mode": "percentage",
          "value": 0.05,
          "table": "payments"
        }
      ]
    },
    "thresholds": {
      "minimum_precision": 0.8,
      "minimum_recall": 0.9
    }
  }'
```

## 2. Launch a fresh benchmark run

This creates a benchmark run, snapshots benchmark configuration, starts Scenario Builder generation in the background, and returns quickly.

```bash
curl -s -X POST "$DATAFORGE_API/api/v1/benchmarks/<benchmark_id>/runs" \
  -H "X-API-Key: $DATAFORGE_API_KEY" \
  -H "Idempotency-Key: payment-retry-run-001" \
  -H "Content-Type: application/json" \
  -d '{
    "seed_mode": "fixed",
    "seed": 42,
    "detector_mode": "manual_upload"
  }'
```

Response:

```json
{
  "benchmark_run_id": "...",
  "status": "queued"
}
```

## 3. Poll benchmark run status

```bash
curl -s "$DATAFORGE_API/api/v1/benchmark-runs/<benchmark_run_id>" \
  -H "X-API-Key: $DATAFORGE_API_KEY"
```

Lifecycle:

```text
queued → generating → waiting_for_detector → detector_received → evaluating → completed
```

Failure states:

```text
generation_failed
evaluation_failed
cancelled
```

When status is `waiting_for_detector`, the dataset, ground truth, and artifact manifest are ready.

## 4. Download artifacts

Get artifact manifest:

```bash
curl -s "$DATAFORGE_API/api/v1/benchmark-runs/<benchmark_run_id>/artifact-manifest" \
  -H "X-API-Key: $DATAFORGE_API_KEY"
```

Common artifact URLs in the manifest:

- dataset ZIP: `/api/v1/runs/<scenario_run_id>/download`
- dataset manifest: `/api/v1/scenario-library/runs/<scenario_run_id>/manifest`
- ground truth JSON: `/api/v1/scenario-library/runs/<scenario_run_id>/ground-truth?format=json`
- ground truth JSONL: `/api/v1/scenario-library/runs/<scenario_run_id>/ground-truth?format=jsonl`
- ground truth CSV: `/api/v1/scenario-library/runs/<scenario_run_id>/ground-truth?format=csv`

## 5. Detector output contract

```bash
curl -s "$DATAFORGE_API/api/v1/evaluations/detector-contract" \
  -H "X-API-Key: $DATAFORGE_API_KEY"
```

Detector JSON shape:

```json
{
  "detector_name": "my-detector",
  "detector_version": "1.0.0",
  "detections": [
    {
      "evaluation_unit": "entity",
      "evaluation_key": {"payment_id": "PAY123"},
      "predicted_failure": true,
      "predicted_failure_type": "duplicate_payment",
      "confidence": 0.98
    }
  ]
}
```

CSV shape:

```csv
evaluation_unit,key_payment_id,predicted_failure,predicted_failure_type,confidence
entity,PAY123,true,duplicate_payment,0.98
```

## 6. Submit detector output by API

```bash
curl -s -X POST "$DATAFORGE_API/api/v1/benchmark-runs/<benchmark_run_id>/detector-output" \
  -H "X-API-Key: $DATAFORGE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "detector_name": "my-detector",
    "detector_version": "1.0.0",
    "detector_output_format": "json",
    "detections": [
      {
        "evaluation_unit": "entity",
        "evaluation_key": {"payment_id": "PAY123"},
        "predicted_failure": true,
        "predicted_failure_type": "duplicate_payment",
        "confidence": 0.98
      }
    ]
  }'
```

## 7. Submit detector output by file upload

Supported extensions:

- `.json`
- `.jsonl`
- `.csv`

```bash
curl -s -X POST "$DATAFORGE_API/api/v1/benchmark-runs/<benchmark_run_id>/detector-output/upload?detector_name=my-detector" \
  -H "X-API-Key: $DATAFORGE_API_KEY" \
  -F "file=@detector_output.jsonl"
```

Uploads are UTF-8 text only, size-limited by `BENCHMARK_DETECTOR_UPLOAD_MAX_BYTES`, and never executed.

## 8. Read final result

```bash
curl -s "$DATAFORGE_API/api/v1/benchmark-runs/<benchmark_run_id>" \
  -H "X-API-Key: $DATAFORGE_API_KEY"
```

Completed run fields include:

- `status`
- `result`
- `metrics.precision`
- `metrics.recall`
- `metrics.f1`
- `metrics.true_positive`
- `metrics.false_positive`
- `metrics.false_negative`
- `acceptance.status`

## Idempotency

Use `Idempotency-Key` when launching benchmark runs. Same key + same request returns the existing run. Same key + different request returns `IDEMPOTENCY_CONFLICT`.

## Cancellation

```bash
curl -s -X POST "$DATAFORGE_API/api/v1/benchmark-runs/<benchmark_run_id>/cancel" \
  -H "X-API-Key: $DATAFORGE_API_KEY"
```

Queued runs can be cancelled immediately. Running generation may become `cancellation_requested`; DataForge does not claim hard cancellation unless the underlying generation step has actually stopped.

## Polling recommendation

Clients should poll `GET /api/v1/benchmark-runs/{id}` every few seconds while status is `queued` or `generating`. The server does not enforce a polling interval; API rate limits still apply.

## V1 execution model limitation

V1 benchmark orchestration uses the existing FastAPI background-task execution model. This is appropriate for controlled limited beta usage, but it is process-local rather than a durable distributed queue. If the backend process restarts during generation, in-flight background work may need operator review or retry.

Phase 2 should move benchmark execution to a durable worker/queue model before positioning this as enterprise-scale distributed execution.

## Current authorization note

Benchmark APIs use the current DataForge API-key protection. Fine-grained scopes such as `benchmark:execute`, `evaluation:submit`, and `artifact:read` are documented future hardening work and are not yet enforced as separate permissions.
