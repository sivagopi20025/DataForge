def test_generate_api_persists_run_and_files(client):
    response = client.post(
        "/api/v1/generate",
        json={"domain": "logistics", "load_type": "bulk", "format": "json", "records": 10},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["run_id"]

    detail = client.get(f"/api/v1/runs/{payload['run_id']}").json()
    assert detail["domain"] == "logistics"
    assert detail["format"] == "json"
    assert detail["generated_files"]


def test_generate_api_rejects_unknown_domain(client):
    response = client.post(
        "/api/v1/generate",
        json={"domain": "unknown", "load_type": "bulk", "format": "json", "records": 10},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "DATAFORGE_ERROR"
