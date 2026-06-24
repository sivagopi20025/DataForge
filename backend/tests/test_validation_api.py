def test_validation_api_persists_results(client):
    generated = client.post(
        "/api/v1/generate",
        json={"domain": "healthcare", "load_type": "bulk", "format": "json", "records": 10},
    ).json()
    generated = client.get(f"/api/v1/jobs/{generated['job_id']}").json()

    response = client.post("/api/v1/validate", json={"run_id": generated["run_id"]})
    assert response.status_code == 200
    assert response.json()["overall_status"] == "PASS"

    detail = client.get(f"/api/v1/runs/{generated['run_id']}").json()
    assert detail["validation_results"]
    assert detail["validation_results"][0]["quality_score"] == response.json()["quality_score"]


def test_validation_api_missing_run_returns_error(client):
    response = client.post("/api/v1/validate", json={"run_id": "missing"})
    assert response.status_code == 400
    assert response.json()["code"] == "DATAFORGE_ERROR"
