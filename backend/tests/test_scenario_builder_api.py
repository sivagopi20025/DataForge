from __future__ import annotations


def test_scenario_builder_configuration_exposes_required_tables_default_plan_and_quality(client):
    response = client.get("/api/v1/scenario-library/scenarios/ecommerce_payment_retry/configuration", params={"records": 1000})
    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario"]["scenario_id"] == "ecommerce_payment_retry"
    assert payload["scenario"]["v1_ready"] is True
    assert payload["required_tables"]
    assert any(table["role"] == "primary scenario table" for table in payload["required_tables"])
    assert payload["default_failure_plan"]["failures"][0]["primitive_id"]
    assert payload["default_failure_plan"]["failures"][0]["estimated_affected"] > 0
    assert payload["compatible_primitives"]
    assert payload["parameter_schema"]["overlap_mode"]["allowed"] == ["non_overlapping", "allow_overlap"]


def test_scenario_library_filter_prefers_v1_ready_executable_scenarios(client):
    response = client.get(
        "/api/v1/scenario-library/scenarios",
        params={"domain": "manufacturing", "execution_status": "executable", "v1_ready": True, "limit": 100},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 48
    assert all(item["execution_status"] == "executable" for item in payload["items"])
    assert all(item["v1_ready"] for item in payload["items"])
    assert all(item["failure_display_name"] for item in payload["items"])

    runtime = client.get(
        "/api/v1/scenario-library/scenarios",
        params={"domain": "manufacturing", "v1_ready": True, "limit": 100},
    ).json()
    assert runtime["total"] == 49


def test_failure_plan_preview_supports_percentage_exact_count_and_overlap_modes(client):
    config = client.get("/api/v1/scenario-library/scenarios/ecommerce_payment_retry/configuration", params={"records": 1000}).json()
    primitive = config["default_failure_plan"]["failures"][0]["primitive_id"]
    plan = {
        "scenario_id": "ecommerce_payment_retry",
        "seed": 123,
        "overlap_mode": "non_overlapping",
        "failures": [
            {"primitive_id": primitive, "mode": "percentage", "value": 0.05, "table": "payments"},
            {"primitive_id": primitive, "mode": "exact_count", "value": 7, "table": "payments"},
        ],
    }
    response = client.post("/api/v1/scenario-library/failure-plan/preview", json={"scenario_id": "ecommerce_payment_retry", "records": 1000, "failure_plan": plan})
    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True
    assert payload["failures"][0]["estimated_affected"] == 50
    assert payload["failures"][1]["estimated_affected"] == 7
    assert payload["overlap_mode"] == "non_overlapping"


def test_failure_plan_preview_rejects_incompatible_primitive(client):
    plan = {
        "scenario_id": "ecommerce_payment_retry",
        "seed": 123,
        "overlap_mode": "allow_overlap",
        "failures": [
            {"primitive_id": "geographic_jump", "mode": "percentage", "value": 0.05, "table": "payments"},
        ],
    }
    response = client.post("/api/v1/scenario-library/failure-plan/preview", json={"scenario_id": "ecommerce_payment_retry", "records": 1000, "failure_plan": plan})
    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["errors"]


def test_scenario_builder_generate_persists_ground_truth_requested_selected_actual_detected(client):
    config = client.get("/api/v1/scenario-library/scenarios/ecommerce_payment_retry/configuration", params={"records": 120}).json()
    plan = {
        "scenario_id": "ecommerce_payment_retry",
        "seed": 919,
        "overlap_mode": "allow_overlap",
        "failures": [
            {
                "primitive_id": config["default_failure_plan"]["failures"][0]["primitive_id"],
                "mode": "percentage",
                "value": 0.05,
                "table": config["default_failure_plan"]["failures"][0]["target_table"],
            }
        ],
    }
    response = client.post(
        "/api/v1/scenario-library/generate",
        json={"scenario_id": "ecommerce_payment_retry", "records": 120, "output_format": "csv", "seed": 919, "severity": "medium", "failure_plan": plan},
    )
    assert response.status_code == 200
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    assert job["status"] == "completed"
    run_id = job["run_id"]
    detail = client.get(f"/api/v1/runs/{run_id}").json()
    report = detail["scenario_reports"]["scenario_execution_report.json"]
    assert report["scenario_outcome"] in {"PASS", "PARTIAL"}
    assert report["ground_truth"]
    row = report["ground_truth"][0]
    assert {"requested", "expected_count", "selected_count", "actual_count", "detected_count", "evidence"} <= set(row)
    assert row["actual_count"] > 0
    assert row["detected_count"] >= row["actual_count"]


def test_saved_scenario_template_crud_validation_and_prepare_run(client):
    config = client.get("/api/v1/scenario-library/scenarios/ecommerce_payment_retry/configuration", params={"records": 100}).json()
    plan = {
        "scenario_id": "ecommerce_payment_retry",
        "seed": 515,
        "overlap_mode": "non_overlapping",
        "failures": [
            {
                "primitive_id": config["default_failure_plan"]["failures"][0]["primitive_id"],
                "mode": "exact_count",
                "value": 5,
                "table": config["default_failure_plan"]["failures"][0]["target_table"],
            }
        ],
    }

    created = client.post(
        "/api/v1/scenario-library/templates",
        json={
            "name": "E-commerce Checkout Failures",
            "description": "Reusable checkout stress template",
            "scenario_id": "ecommerce_payment_retry",
            "records": 100,
            "output_format": "csv",
            "seed_behavior": "fixed_seed",
            "failure_plan": plan,
        },
    )
    assert created.status_code == 200
    template = created.json()
    assert template["compatibility"]["valid"] is True
    assert template["failure_count"] == 1

    listed = client.get("/api/v1/scenario-library/templates").json()
    assert listed["items"][0]["name"] == "E-commerce Checkout Failures"

    updated = client.patch(f"/api/v1/scenario-library/templates/{template['id']}", json={"name": "Checkout Failure Regression"}).json()
    assert updated["name"] == "Checkout Failure Regression"

    prepared = client.post(f"/api/v1/scenario-library/templates/{template['id']}/prepare-run").json()
    assert prepared["status"] == "READY"
    assert prepared["generation_request"]["failure_plan"]["seed"] == 515

    deleted = client.delete(f"/api/v1/scenario-library/templates/{template['id']}").json()
    assert deleted["deleted"] is True


def test_scenario_builder_run_history_rerun_and_comparison(client):
    config = client.get("/api/v1/scenario-library/scenarios/ecommerce_payment_retry/configuration", params={"records": 100}).json()

    def run(seed: int) -> str:
        plan = {
            "scenario_id": "ecommerce_payment_retry",
            "seed": seed,
            "overlap_mode": "allow_overlap",
            "failures": [
                {
                    "primitive_id": config["default_failure_plan"]["failures"][0]["primitive_id"],
                    "mode": "percentage",
                    "value": 0.05,
                    "table": config["default_failure_plan"]["failures"][0]["target_table"],
                }
            ],
        }
        response = client.post(
            "/api/v1/scenario-library/generate",
            json={"scenario_id": "ecommerce_payment_retry", "records": 100, "output_format": "csv", "seed": seed, "severity": "medium", "failure_plan": plan},
        )
        job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
        assert job["status"] == "completed"
        return job["run_id"]

    left_id = run(710)
    right_id = run(711)

    history = client.get("/api/v1/scenario-library/runs").json()
    assert history["total"] >= 2
    first = history["items"][0]
    assert first["failure_plan"]
    assert first["ground_truth_summary"]["actual_count"] > 0
    assert first["ground_truth_summary"]["detection_rate"] >= 1

    rerun = client.post(f"/api/v1/scenario-library/runs/{left_id}/prepare-rerun").json()
    assert rerun["generation_request"]["scenario_id"] == "ecommerce_payment_retry"
    assert rerun["generation_request"]["failure_plan"]["seed"] == 710

    comparison = client.post("/api/v1/scenario-library/runs/compare", json={"left_run_id": left_id, "right_run_id": right_id}).json()
    assert comparison["comparison"]["left"]["actual_count"] > 0
    assert "detection_rate" in comparison["comparison"]["delta"]
