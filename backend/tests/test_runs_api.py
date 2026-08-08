def test_runs_api_lists_and_returns_details(client):
    first_job = client.post("/api/v1/generate", json={"domain": "finance", "load_type": "bulk", "format": "csv", "records": 8}).json()
    first = client.get(f"/api/v1/jobs/{first_job['job_id']}").json()
    client.post("/api/v1/generate", json={"domain": "banking", "load_type": "bulk", "format": "json", "records": 8})

    response = client.get("/api/v1/runs?limit=1&offset=0")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["limit"] == 1
    assert len(payload["items"]) == 1

    detail = client.get(f"/api/v1/runs/{first['run_id']}")
    assert detail.status_code == 200
    assert detail.json()["generated_files"]
