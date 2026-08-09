from __future__ import annotations


def _benchmark_definition(client, *, seed: int = 3131) -> dict:
    config = client.get("/api/v1/scenario-library/scenarios/ecommerce_payment_retry/configuration", params={"records": 120}).json()
    primitive = config["default_failure_plan"]["failures"][0]
    plan = {
        "scenario_id": "ecommerce_payment_retry",
        "seed": seed,
        "overlap_mode": "allow_overlap",
        "failures": [
            {
                "primitive_id": primitive["primitive_id"],
                "mode": "percentage",
                "value": 0.05,
                "table": primitive["target_table"],
            }
        ],
    }
    response = client.post(
        "/api/v1/benchmarks",
        json={
            "name": f"Payment Retry Benchmark {seed}",
            "domain": "ecommerce",
            "scenario_id": "ecommerce_payment_retry",
            "records": 120,
            "output_format": "csv",
            "seed": seed,
            "failure_plan": plan,
            "thresholds": {"minimum_recall": 0.9, "minimum_precision": 0.8},
        },
    )
    assert response.status_code == 200
    return response.json()


def _launch(client, benchmark_id: str, *, seed: int = 3131, key: str = "benchmark-run-key") -> dict:
    response = client.post(
        f"/api/v1/benchmarks/{benchmark_id}/runs",
        headers={"Idempotency-Key": key},
        json={"seed": seed, "seed_mode": "fixed", "detector_mode": "manual_upload"},
    )
    assert response.status_code == 200
    benchmark_run_id = response.json()["benchmark_run_id"]
    detail = client.get(f"/api/v1/benchmark-runs/{benchmark_run_id}")
    assert detail.status_code == 200
    return detail.json()


def _detections(client, scenario_run_id: str) -> list[dict]:
    ground_truth = client.get(f"/api/v1/scenario-library/runs/{scenario_run_id}/ground-truth").json()
    return [
        {
            "evaluation_unit": failure["evaluation_unit"],
            "evaluation_key": failure["evaluation_key"],
            "predicted_failure": True,
            "predicted_failure_type": failure["failure_category"],
            "confidence": 0.99,
        }
        for failure in ground_truth["failures"]
    ]


def test_benchmark_definition_launches_fresh_scenario_run_and_artifacts(client):
    benchmark = _benchmark_definition(client)
    run = _launch(client, benchmark["id"], key="fresh-generation")

    assert run["status"] == "waiting_for_detector"
    assert run["scenario_run_id"]
    assert run["generation_job_id"]
    assert run["dataset_status"] == "ready"
    assert run["ground_truth_status"] == "ready"
    assert run["snapshot"]["benchmark_id"] == benchmark["id"]
    assert run["snapshot"]["failure_plan"]["seed"] == benchmark["seed"]
    assert run["artifact_manifest"]["benchmark_run_id"] == run["id"]
    assert run["artifact_manifest"]["artifacts"]["dataset"]

    manifest = client.get(f"/api/v1/benchmark-runs/{run['id']}/artifact-manifest").json()
    assert manifest["scenario_run_id"] == run["scenario_run_id"]
    assert manifest["checksums"]["ground_truth_jsonl_sha256"]


def test_benchmark_run_idempotency_and_conflict(client):
    benchmark = _benchmark_definition(client, seed=3132)
    first = client.post(
        f"/api/v1/benchmarks/{benchmark['id']}/runs",
        headers={"Idempotency-Key": "same-key"},
        json={"seed": 3132, "seed_mode": "fixed", "detector_mode": "manual_upload"},
    ).json()
    second = client.post(
        f"/api/v1/benchmarks/{benchmark['id']}/runs",
        headers={"Idempotency-Key": "same-key"},
        json={"seed": 3132, "seed_mode": "fixed", "detector_mode": "manual_upload"},
    ).json()
    assert first["benchmark_run_id"] == second["benchmark_run_id"]

    conflict = client.post(
        f"/api/v1/benchmarks/{benchmark['id']}/runs",
        headers={"Idempotency-Key": "same-key"},
        json={"seed": 9999, "seed_mode": "fixed", "detector_mode": "manual_upload"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_benchmark_concurrency_limit_is_enforced(client, monkeypatch):
    import backend.app.api.v1.routes as routes

    monkeypatch.setenv("BENCHMARK_CONCURRENT_RUNS", "1")
    from backend.app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(routes, "_execute_benchmark_run", lambda *args, **kwargs: None)
    benchmark = _benchmark_definition(client, seed=3140)

    first = client.post(
        f"/api/v1/benchmarks/{benchmark['id']}/runs",
        headers={"Idempotency-Key": "concurrency-one"},
        json={"seed": 3140, "seed_mode": "fixed", "detector_mode": "manual_upload"},
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/v1/benchmarks/{benchmark['id']}/runs",
        headers={"Idempotency-Key": "concurrency-two"},
        json={"seed": 3141, "seed_mode": "fixed", "detector_mode": "manual_upload"},
    )
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "QUOTA_EXCEEDED"
    get_settings.cache_clear()


def test_detector_submission_runs_automatic_evaluation_and_blocks_duplicates(client):
    benchmark = _benchmark_definition(client, seed=3133)
    run = _launch(client, benchmark["id"], seed=3133, key="auto-eval")
    detections = _detections(client, run["scenario_run_id"])

    completed = client.post(
        f"/api/v1/benchmark-runs/{run['id']}/detector-output",
        json={"detector_name": "perfect-detector", "detections": detections},
    )
    assert completed.status_code == 200
    payload = completed.json()
    assert payload["status"] == "completed"
    assert payload["result"] == "PASS"
    assert payload["metrics"]["true_positive"] == len(detections)
    assert payload["metrics"]["recall"] == 1

    duplicate = client.post(
        f"/api/v1/benchmark-runs/{run['id']}/detector-output",
        json={"detector_name": "perfect-detector", "detections": detections},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "INVALID_BENCHMARK_STATE"


def test_detector_upload_accepts_csv_and_rejects_unsupported_file(client):
    benchmark = _benchmark_definition(client, seed=3134)
    run = _launch(client, benchmark["id"], seed=3134, key="upload-eval")
    ground_truth = client.get(f"/api/v1/scenario-library/runs/{run['scenario_run_id']}/ground-truth").json()
    first = ground_truth["failures"][0]
    key_name, key_value = next(iter(first["evaluation_key"].items()))
    csv_payload = (
        f"evaluation_unit,key_{key_name},predicted_failure,predicted_failure_type,confidence\n"
        f"{first['evaluation_unit']},{key_value},true,{first['failure_category']},0.91\n"
    )

    uploaded = client.post(
        f"/api/v1/benchmark-runs/{run['id']}/detector-output/upload",
        params={"detector_name": "csv-detector"},
        files={"file": ("detector.csv", csv_payload, "text/csv")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["status"] == "completed"
    assert uploaded.json()["metrics"]["true_positive"] == 1

    second = _launch(client, benchmark["id"], seed=3135, key="bad-upload")
    rejected = client.post(
        f"/api/v1/benchmark-runs/{second['id']}/detector-output/upload",
        files={"file": ("detector.txt", "not supported", "text/plain")},
    )
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "INVALID_DETECTOR_OUTPUT"


def test_benchmark_run_list_filters_and_concurrent_isolation(client):
    benchmark = _benchmark_definition(client, seed=3136)
    left = _launch(client, benchmark["id"], seed=3136, key="isolation-left")
    right = _launch(client, benchmark["id"], seed=3137, key="isolation-right")

    assert left["id"] != right["id"]
    assert left["scenario_run_id"] != right["scenario_run_id"]
    listed = client.get("/api/v1/benchmark-runs", params={"benchmark_id": benchmark["id"], "status": "waiting_for_detector", "limit": 10}).json()
    ids = {item["id"] for item in listed["items"]}
    assert {left["id"], right["id"]} <= ids


def test_benchmark_run_cancel_rejects_completed_runs(client):
    benchmark = _benchmark_definition(client, seed=3138)
    run = _launch(client, benchmark["id"], seed=3138, key="cancel-completed")
    detections = _detections(client, run["scenario_run_id"])
    completed = client.post(f"/api/v1/benchmark-runs/{run['id']}/detector-output", json={"detector_name": "perfect-detector", "detections": detections}).json()
    assert completed["status"] == "completed"

    cancelled = client.post(f"/api/v1/benchmark-runs/{run['id']}/cancel")
    assert cancelled.status_code == 409
    assert cancelled.json()["error"]["code"] == "INVALID_BENCHMARK_STATE"
