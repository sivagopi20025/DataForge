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


def test_quality_analytics_average_scores_by_run_not_check_count(client):
    first = client.post(
        "/api/v1/generate",
        json={"domain": "healthcare", "load_type": "bulk", "format": "json", "records": 8, "selected_tables": ["patients"]},
    ).json()
    second = client.post(
        "/api/v1/generate",
        json={"domain": "healthcare", "load_type": "bulk", "format": "json", "records": 8, "selected_tables": ["patients"], "issues": {"schema_drift": 1}},
    ).json()

    first_score = client.get(f"/api/v1/runs/{first['run_id']}").json()["validation_results"][0]["quality_score"]
    second_score = client.get(f"/api/v1/runs/{second['run_id']}").json()["validation_results"][0]["quality_score"]

    overview_score = client.get("/api/v1/admin/analytics/overview").json()["average_quality_score"]
    domain_score = client.get("/api/v1/admin/analytics/quality/domains").json()["healthcare"]

    expected = round((first_score + second_score) / 2, 2)
    assert overview_score == expected
    assert domain_score == expected
