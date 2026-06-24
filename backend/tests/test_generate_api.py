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
    assert detail["validation_results"]
    assert detail["validation_results"][0]["quality_score"] is not None


def test_generated_file_download_api_streams_file(client):
    response = client.post(
        "/api/v1/generate",
        json={"domain": "logistics", "load_type": "bulk", "format": "json", "records": 10, "selected_tables": ["customers"]},
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    detail = client.get(f"/api/v1/runs/{run_id}").json()
    generated_file = detail["generated_files"][0]

    download = client.get(f"/api/v1/runs/{run_id}/files/{generated_file['id']}/download")

    assert download.status_code == 200
    assert "attachment" in download.headers["content-disposition"]
    assert generated_file["file_name"] in download.headers["content-disposition"]
    assert download.content


def test_generate_api_rejects_unknown_domain(client):
    response = client.post(
        "/api/v1/generate",
        json={"domain": "unknown", "load_type": "bulk", "format": "json", "records": 10},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "DATAFORGE_ERROR"


def test_catalog_tables_api_returns_domain_tables(client):
    response = client.get("/api/v1/catalog/tables/healthcare")
    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "healthcare"
    table_names = {table["name"] for table in payload["tables"]}
    assert {"patients", "visits", "claims", "payments"}.issubset(table_names)


def test_generate_api_accepts_selected_tables_and_issue_rates(client):
    response = client.post(
        "/api/v1/generate",
        json={
            "domain": "banking",
            "load_type": "bulk",
            "format": "json",
            "records": 10,
            "selected_tables": ["customers", "deposit_accounts"],
            "issues": {"null_values": 5, "duplicate_records": 5},
        },
    )
    assert response.status_code == 200
    payload = response.json()

    detail = client.get(f"/api/v1/runs/{payload['run_id']}").json()
    generated_names = {file["file_name"] for file in detail["generated_files"]}
    assert generated_names == {"customers.json", "deposit_accounts.json"}
    assert {issue["issue_type"] for issue in detail["issue_manifest"]}.intersection({"null_values", "duplicate_records"})
