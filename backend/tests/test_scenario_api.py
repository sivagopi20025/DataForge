from __future__ import annotations

import io
import json
import zipfile

import pytest


def test_scenario_api_lists_filters_and_searches(client):
    response = client.get("/api/v1/scenarios")
    assert response.status_code == 200
    assert response.json()["total"] == 50

    banking = client.get("/api/v1/scenarios/domains/banking").json()
    assert banking["total"] == 5

    search = client.get("/api/v1/scenarios/search", params={"q": "ghost provider"}).json()
    assert search["items"][0]["scenario_id"] == "healthcare_ghost_provider"

    detail = client.get("/api/v1/scenarios/banking_duplicate_transfer").json()
    assert detail["scenario_id"] == "banking_duplicate_transfer"
    assert detail["failure_injections"]


def test_scenario_library_api_exposes_registered_vs_runtime_capable_counts(client):
    summary = client.get("/api/v1/scenario-library/summary").json()
    assert summary["total_registered"] == 760
    assert summary["total_rejected"] == 36
    assert summary["runtime_registry_count"] == 50
    assert summary["total_executable"] == 521
    assert summary["total_runtime_capable"] == 531
    assert summary["total_specification_only"] > 0
    assert summary["execution_status_counts"]["executable"] == summary["total_executable"]
    assert summary["executable_by_domain"]
    assert summary["blocked_by_capability"]
    assert summary["blocked_by_schema_type"]
    assert summary["blocked_by_dependency_category"]

    executable = client.get("/api/v1/scenario-library/scenarios", params={"execution_status": "executable", "limit": 5}).json()
    assert executable["total"] == summary["total_executable"]
    assert executable["items"]
    assert executable["items"][0]["execution_status"] == "executable"
    assert executable["items"][0]["requirement_resolution"]["execution_supported"] is True
    assert "semantic_requirements" in executable["items"][0]
    assert "resolved_columns" in executable["items"][0]["semantic_requirements"]

    quality = client.get("/api/v1/scenario-library/quality-summary").json()
    assert quality["total_runtime_capable"] == 531
    assert quality["v1_ready"] == 531
    assert quality["needs_fix"] == 0


def test_scenario_api_validates_config(client):
    response = client.post(
        "/api/v1/scenarios/banking_duplicate_transfer/validate-config",
        json={"scenario_id": "ignored", "records": 100, "output_format": "csv"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "PASS"
    assert payload["resolved_config"]["domain"] == "banking"


def test_scenario_api_runs_reference_scenario_and_zip_contains_reports(client):
    response = client.post(
        "/api/v1/scenarios/retail_payment_retry/run",
        json={"scenario_id": "ignored", "records": 100, "output_format": "csv", "severity": "low"},
    )
    assert response.status_code == 200
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    assert job["status"] == "completed"
    run_id = job["run_id"]

    scenario_run = client.get(f"/api/v1/scenario-runs/{run_id}").json()
    assert scenario_run["scenario_reports"]["scenario_definition.json"]["scenario_id"] == "retail_payment_retry"

    download = client.get(f"/api/v1/runs/{run_id}/download")
    assert download.status_code == 200
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        names = set(archive.namelist())
        assert {
            "reports/scenario_definition.json",
            "reports/scenario_run_config.json",
            "reports/scenario_execution_report.json",
            "reports/expected_validations.json",
        } <= names
        definition = json.loads(archive.read("reports/scenario_definition.json"))
        execution = json.loads(archive.read("reports/scenario_execution_report.json"))
        readme = archive.read("README.md").decode()
        assert definition["scenario_id"] == "retail_payment_retry"
        assert execution["scenario_outcome"] == "PASS"
        assert execution["requested_failure_counts"]
        assert execution["selected_target_counts"]
        assert execution["actual_mutation_counts"]
        assert execution["detected_issue_counts"]
        assert execution["reconciliation_by_failure"]
        assert "Scenario: Retail Payment Retry" in readme

    detail = client.get(f"/api/v1/runs/{run_id}").json()
    assert detail["scenario_name"] == "Retail Payment Retry"
    assert detail["scenario_outcome"] == "PASS"
    assert detail["scenario_severity"] == "low"


@pytest.mark.parametrize(
    "scenario_id,expected_validation",
    [
        ("logistics_cold_chain_failure", "temperature_breach_detected"),
        ("finance_settlement_delay", "settlement_delay_detected"),
        ("insurance_coverage_exceeded", "coverage_limit_exceeded"),
        ("education_grade_calculation_error", "grade_formula_mismatch"),
        ("ecommerce_inventory_oversell", "inventory_oversell_detected"),
    ],
)
def test_phase_d3_reference_scenario_api_reports_authoritative_validators(client, scenario_id, expected_validation):
    response = client.post(
        f"/api/v1/scenarios/{scenario_id}/run",
        json={"scenario_id": "ignored", "records": 120, "output_format": "csv", "severity": "low"},
    )
    assert response.status_code == 200
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    assert job["status"] == "completed"
    run_id = job["run_id"]

    detail = client.get(f"/api/v1/runs/{run_id}").json()
    assert detail["scenario_id"] == scenario_id
    assert detail["scenario_outcome"] == "PASS"

    scenario_run = client.get(f"/api/v1/scenario-runs/{run_id}").json()
    execution = scenario_run["scenario_reports"]["scenario_execution_report.json"]
    validator_results = execution["scenario_validator_results"]
    assert execution["scenario_outcome"] == "PASS"
    assert any(item["validation_id"] == expected_validation for item in validator_results)
    for item in validator_results:
        assert item["evidence"]
        assert item["detected_count"] >= item["expected_count"]
        assert item["reconciliation_status"] == "PASS"


def test_telecom_scenario_stream_execution_validation_stop_and_replay(client):
    response = client.post(
        "/api/v1/scenarios/telecom_tower_congestion/stream/start",
        json={
            "scenario_id": "ignored",
            "mode": "streaming",
            "event_rate": 10,
            "duration_seconds": 60,
            "severity": "high",
            "variation_ids": ["delayed_network_events"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    stream_id = payload["stream_id"]
    token = payload["stream_token"]

    status = client.get(f"/api/v1/streams/{stream_id}").json()
    assert status["status"] == "completed"
    assert status["failure_summary"]["tower_congestion"] > 0

    events = client.get(f"/api/v1/streams/{stream_id}/events", headers={"Authorization": f"Bearer {token}"}).json()
    assert events["events"]
    assert any("tower_congestion" in event["injected_issues"] for event in events["events"])
    assert all(event["correlation_id"] for event in events["events"])
    assert all(event["sequence_number"] for event in events["events"])

    validation = client.get(f"/api/v1/streams/{stream_id}/validation").json()
    assert validation["scenario_outcome"] in {"PASS", "PARTIAL"}
    assert validation["scenario_validator_results"]

    replay = client.post(f"/api/v1/streams/{stream_id}/replay").json()
    assert replay["events"]

    stopped = client.post(f"/api/v1/streams/{stream_id}/stop").json()
    assert stopped["status"] == "completed"
