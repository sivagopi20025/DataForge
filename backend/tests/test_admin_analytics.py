def test_admin_analytics_endpoints(client):
    client.post("/api/v1/generate", json={"domain": "insurance", "load_type": "bulk", "format": "json", "records": 8})
    client.post("/api/v1/generate", json={"domain": "retail", "load_type": "cdc", "format": "json", "records": 8})

    overview = client.get("/api/v1/admin/analytics/overview")
    assert overview.status_code == 200
    assert overview.json()["datasets_generated"] == 2
    assert overview.json()["files_generated"] >= 2
    assert overview.json()["active_users"] == 1

    assert client.get("/api/v1/admin/analytics/domains").json()["insurance"] == 1
    assert client.get("/api/v1/admin/analytics/formats").json()["json"] == 2
    assert client.get("/api/v1/admin/analytics/load-types").json()["bulk"] == 1

    run_id = client.get("/api/v1/runs").json()["items"][0]["id"]
    client.post("/api/v1/validate", json={"run_id": run_id})
    assert client.get("/api/v1/admin/analytics/quality/domains").json()
    assert client.get("/api/v1/admin/analytics/quality/load-types").json()
    assert client.get("/api/v1/admin/analytics/quality/trends").json()
    assert client.get("/api/v1/admin/analytics/quality/highest-runs").json()
    assert client.get("/api/v1/admin/analytics/quality/lowest-runs").json()
