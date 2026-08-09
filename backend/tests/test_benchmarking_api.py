from __future__ import annotations

import json

from dataforge.scenarios.benchmarking import detector_payload_from_csv, detector_payload_from_jsonl, evaluate_detector_output


def _scenario_run(client, *, records: int = 140, seed: int = 1717) -> str:
    config = client.get("/api/v1/scenario-library/scenarios/ecommerce_payment_retry/configuration", params={"records": records}).json()
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
        "/api/v1/scenario-library/generate",
        json={"scenario_id": "ecommerce_payment_retry", "records": records, "output_format": "csv", "seed": seed, "severity": "medium", "failure_plan": plan},
    )
    assert response.status_code == 200
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    assert job["status"] == "completed"
    return job["run_id"]


def _detections_from_ground_truth(ground_truth: dict) -> list[dict]:
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


def test_ground_truth_exports_and_manifest(client):
    run_id = _scenario_run(client)

    json_response = client.get(f"/api/v1/scenario-library/runs/{run_id}/ground-truth", params={"format": "json"})
    assert json_response.status_code == 200
    ground_truth = json_response.json()
    assert ground_truth["ground_truth_version"] == "1.0"
    assert ground_truth["run_id"] == run_id
    assert ground_truth["failures"]
    assert ground_truth["evaluation_units"][0]["candidate_count"] >= len(ground_truth["failures"])

    jsonl_response = client.get(f"/api/v1/scenario-library/runs/{run_id}/ground-truth", params={"format": "jsonl"})
    assert jsonl_response.status_code == 200
    assert b'"type": "metadata"' in jsonl_response.content
    assert b'"type": "failure"' in jsonl_response.content

    csv_response = client.get(f"/api/v1/scenario-library/runs/{run_id}/ground-truth", params={"format": "csv"})
    assert csv_response.status_code == 200
    assert b"failure_instance_id" in csv_response.content

    manifest = client.get(f"/api/v1/scenario-library/runs/{run_id}/manifest").json()
    assert manifest["manifest_version"] == "1.0"
    assert manifest["ground_truth_artifacts"]["jsonl"]["checksum_sha256"]
    assert manifest["generated_files"]
    assert manifest["tables"]


def test_detector_evaluation_scores_true_positive_false_positive_and_false_negative(client):
    run_id = _scenario_run(client, seed=1718)
    ground_truth = client.get(f"/api/v1/scenario-library/runs/{run_id}/ground-truth").json()
    detections = _detections_from_ground_truth(ground_truth)

    perfect = client.post(
        "/api/v1/evaluations",
        json={"run_id": run_id, "detector_name": "perfect-detector", "detections": detections},
    )
    assert perfect.status_code == 200
    perfect_payload = perfect.json()
    assert perfect_payload["metrics"]["true_positive"] == len(ground_truth["failures"])
    assert perfect_payload["metrics"]["false_negative"] == 0
    assert perfect_payload["metrics"]["precision"] == 1
    assert perfect_payload["metrics"]["recall"] == 1

    truth_hashes = {failure["evaluation_key_hash"] for failure in ground_truth["failures"]}
    healthy_key = None
    for unit in ground_truth["evaluation_units"]:
        for candidate_key, key_hash in zip(unit["candidate_keys"], unit["candidate_key_hashes"], strict=False):
            if key_hash not in truth_hashes:
                healthy_key = {"evaluation_unit": unit["evaluation_unit"], "evaluation_key": candidate_key}
                break
        if healthy_key:
            break
    assert healthy_key is not None
    noisy = client.post(
        "/api/v1/evaluations",
        json={"run_id": run_id, "detector_name": "noisy-detector", "detections": [detections[0], healthy_key]},
    ).json()
    assert noisy["metrics"]["true_positive"] == 1
    assert noisy["metrics"]["false_positive"] == 1
    assert noisy["metrics"]["false_negative"] == len(ground_truth["failures"]) - 1


def test_benchmark_definition_and_acceptance_thresholds(client):
    run_id = _scenario_run(client, seed=1719)
    run_detail = client.get(f"/api/v1/scenario-library/runs/{run_id}").json()
    ground_truth = client.get(f"/api/v1/scenario-library/runs/{run_id}/ground-truth").json()
    detections = _detections_from_ground_truth(ground_truth)

    benchmark = client.post(
        "/api/v1/benchmarks",
        json={
            "name": "Payment Retry Detector Benchmark",
            "domain": "ecommerce",
            "scenario_id": "ecommerce_payment_retry",
            "records": run_detail["record_count"],
            "output_format": run_detail["format"],
            "seed": run_detail["failure_plan"]["seed"],
            "failure_plan": run_detail["failure_plan"],
            "thresholds": {"minimum_recall": 0.9, "minimum_precision": 0.8},
        },
    )
    assert benchmark.status_code == 200
    benchmark_id = benchmark.json()["id"]

    passed = client.post(
        f"/api/v1/benchmarks/{benchmark_id}/runs",
        json={"run_id": run_id, "detector_name": "perfect-detector", "detections": detections},
    ).json()
    assert passed["acceptance"]["status"] == "PASS"

    failed = client.post(
        f"/api/v1/benchmarks/{benchmark_id}/runs",
        json={"run_id": run_id, "detector_name": "empty-detector", "detections": []},
    ).json()
    assert failed["acceptance"]["status"] == "FAIL"
    assert failed["metrics"]["recall"] == 0

    assert client.get("/api/v1/benchmarks").json()["items"]
    assert client.get("/api/v1/evaluations").json()["items"]
    assert client.get(f"/api/v1/evaluations/{passed['id']}").json()["id"] == passed["id"]


def test_waiting_for_detector_benchmark_run_can_be_cancelled(client):
    run_id = _scenario_run(client, records=120, seed=1722)
    run_detail = client.get(f"/api/v1/scenario-library/runs/{run_id}").json()
    benchmark = client.post(
        "/api/v1/benchmarks",
        json={
            "name": "Cancelable Waiting Benchmark",
            "domain": "ecommerce",
            "scenario_id": "ecommerce_payment_retry",
            "records": run_detail["record_count"],
            "output_format": run_detail["format"],
            "seed": run_detail["failure_plan"]["seed"],
            "failure_plan": run_detail["failure_plan"],
            "thresholds": {"minimum_recall": 0.9, "minimum_precision": 0.8},
        },
    )
    assert benchmark.status_code == 200

    launched = client.post(
        f"/api/v1/benchmarks/{benchmark.json()['id']}/runs",
        json={"seed": 1722, "seed_mode": "fixed", "detector_mode": "manual_upload"},
    )
    assert launched.status_code == 200
    benchmark_run_id = launched.json()["benchmark_run_id"]
    benchmark_run = client.get(f"/api/v1/benchmark-runs/{benchmark_run_id}").json()
    assert benchmark_run["status"] == "waiting_for_detector"

    cancelled = client.post(f"/api/v1/benchmark-runs/{benchmark_run_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_evaluation_import_accepts_csv_payload(client):
    run_id = _scenario_run(client, seed=1720)
    ground_truth = client.get(f"/api/v1/scenario-library/runs/{run_id}/ground-truth").json()
    first = ground_truth["failures"][0]
    key_name, key_value = next(iter(first["evaluation_key"].items()))
    csv_payload = (
        "evaluation_unit,key_{key_name},predicted_failure,predicted_failure_type,confidence\n"
        "{unit},{key_value},true,{failure_category},0.91\n"
    ).format(key_name=key_name, unit=first["evaluation_unit"], key_value=key_value, failure_category=first["failure_category"])

    response = client.post(
        "/api/v1/evaluations/import",
        json={
            "run_id": run_id,
            "detector_name": "csv-detector",
            "detector_output_format": "csv",
            "payload": csv_payload,
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["metrics"]["true_positive"] == 1
    assert result["metrics"]["false_negative"] == len(ground_truth["failures"]) - 1


def test_detector_contract_and_parsers():
    jsonl = '\n'.join(
        [
            json.dumps({"type": "metadata", "detector_name": "jsonl-demo", "detector_version": "1"}),
            json.dumps({"evaluation_unit": "entity", "evaluation_key": {"payment_id": "PAY1"}, "predicted_failure": True}),
        ]
    )
    assert detector_payload_from_jsonl(jsonl)["detector_name"] == "jsonl-demo"

    csv_payload = "evaluation_unit,key_payment_id,predicted_failure,predicted_failure_type,confidence\nentity,PAY1,true,duplication,0.7\n"
    parsed = detector_payload_from_csv(csv_payload)
    assert parsed["detections"][0]["evaluation_key"] == {"payment_id": "PAY1"}

    result = evaluate_detector_output(
        {"run_id": "run", "failures": [], "evaluation_units": [{"evaluation_unit": "entity", "candidate_key_hashes": []}]},
        {"detector_name": "empty", "detections": []},
    )
    assert result["metrics"]["precision"] is None
    assert result["metrics"]["recall"] is None
