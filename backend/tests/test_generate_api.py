import io
import json
import zipfile

import backend.app.services.generation as generation_module


def test_generate_api_persists_run_and_files(client):
    response = client.post(
        "/api/v1/generate",
        json={"domain": "logistics", "load_type": "bulk", "format": "json", "records": 10},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["job_id"]

    job = client.get(f"/api/v1/jobs/{payload['job_id']}").json()
    assert job["status"] == "completed"
    assert job["run_id"]

    detail = client.get(f"/api/v1/runs/{job['run_id']}").json()
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
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    run_id = job["run_id"]
    detail = client.get(f"/api/v1/runs/{run_id}").json()
    generated_file = detail["generated_files"][0]
    assert generated_file["storage_backend"] == "local"
    assert generated_file["object_key"].endswith(generated_file["file_name"])
    assert generated_file["size_bytes"] > 0
    assert generated_file["content_type"] == "application/json"

    download = client.get(f"/api/v1/runs/{run_id}/files/{generated_file['id']}/download")

    assert download.status_code == 200
    assert "attachment" in download.headers["content-disposition"]
    assert generated_file["file_name"] in download.headers["content-disposition"]
    assert download.content


def test_run_download_api_streams_zip_with_all_files(client):
    response = client.post(
        "/api/v1/generate",
        json={"domain": "healthcare", "load_type": "bulk", "format": "csv", "records": 10, "selected_tables": ["patients", "visits"]},
    )
    assert response.status_code == 200
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    run_id = job["run_id"]

    download = client.get(f"/api/v1/runs/{run_id}/download")

    assert download.status_code == 200
    assert "attachment" in download.headers["content-disposition"]
    assert download.headers["content-type"].startswith("application/zip")
    assert b"patients.csv" in download.content
    assert b"visits.csv" in download.content

    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        names = set(archive.namelist())
        assert {"data/patients.csv", "data/visits.csv"} <= names
        assert {
            "reports/validation_report.json",
            "reports/issue_manifest.json",
            "reports/run_summary.json",
            "reports/alignment_report.json",
            "reports/realism_report.json",
            "README.md",
        } <= names
        summary = json.loads(archive.read("reports/run_summary.json"))
        validation_report = json.loads(archive.read("reports/validation_report.json"))
        issue_manifest = json.loads(archive.read("reports/issue_manifest.json"))
        readme = archive.read("README.md").decode()
        assert summary["run_id"] == run_id
        assert validation_report["run_id"] == run_id
        assert issue_manifest["run_id"] == run_id
        assert "intentionally injected failures" in readme
        assert "Realism Profile: realistic" in readme
        assert "No public/reference dataset rows are copied" in readme


def test_generation_retries_clean_validation_failure_and_includes_retry_report(client, monkeypatch):
    real_validate = generation_module.validate
    calls = {"count": 0}

    def fail_first_clean_validation(data, spec, *args, **kwargs):
        calls["count"] += 1
        report = real_validate(data, spec, *args, **kwargs)
        if calls["count"] == 1:
            report["status"] = "FAIL"
            report["summary"]["failed"] = int(report["summary"].get("failed", 0)) + 1
            report["checks"].append(
                {
                    "name": "simulated_clean_spec_failure",
                    "check": "simulated_clean_spec_failure",
                    "status": "FAIL",
                    "table": "suppliers",
                    "column": "supplier_id",
                    "expected": "valid clean generation",
                    "actual": "simulated failure",
                    "failures": 1,
                }
            )
        return report

    monkeypatch.setattr(generation_module, "validate", fail_first_clean_validation)

    response = client.post(
        "/api/v1/generate",
        json={"domain": "retail", "load_type": "bulk", "format": "csv", "records": 10, "selected_tables": ["suppliers"]},
    )

    assert response.status_code == 200
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    assert job["status"] == "completed"
    run_id = job["run_id"]

    download = client.get(f"/api/v1/runs/{run_id}/download")

    assert download.status_code == 200
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        names = set(archive.namelist())
        assert "reports/generation_retry_report.json" in names
        retry_report = json.loads(archive.read("reports/generation_retry_report.json"))
        run_summary = json.loads(archive.read("reports/run_summary.json"))
        assert retry_report["run_id"] == run_id
        assert retry_report["attempts"] == 2
        assert retry_report["selected_seed"] == 43
        assert retry_report["attempt_history"][0]["status"] == "FAIL"
        assert "reports/generation_retry_report.json" in run_summary["report_files"]


def test_delete_run_api_removes_run_and_generated_files(client):
    response = client.post(
        "/api/v1/generate",
        json={"domain": "retail", "load_type": "bulk", "format": "csv", "records": 10, "selected_tables": ["suppliers"]},
    )
    assert response.status_code == 200
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    run_id = job["run_id"]
    detail = client.get(f"/api/v1/runs/{run_id}").json()
    generated_file = detail["generated_files"][0]

    delete_response = client.delete(f"/api/v1/runs/{run_id}")

    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] == 1
    assert client.get(f"/api/v1/runs/{run_id}").status_code == 400
    assert client.get(f"/api/v1/jobs/{job['job_id']}").json()["run_id"] is None
    assert client.get(f"/api/v1/runs/{run_id}/files/{generated_file['id']}/download").status_code == 400


def test_bulk_delete_runs_api_removes_selected_runs(client):
    run_ids = []
    for domain in ("retail", "healthcare"):
        response = client.post(
            "/api/v1/generate",
            json={"domain": domain, "load_type": "bulk", "format": "json", "records": 5},
        )
        assert response.status_code == 200
        job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
        run_ids.append(job["run_id"])

    delete_response = client.post("/api/v1/runs/delete", json={"run_ids": run_ids})

    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] == 2
    assert set(delete_response.json()["run_ids"]) == set(run_ids)
    for run_id in run_ids:
        assert client.get(f"/api/v1/runs/{run_id}").status_code == 400


def test_generated_file_preview_api_returns_table_rows(client):
    response = client.post(
        "/api/v1/generate",
        json={"domain": "healthcare", "load_type": "bulk", "format": "json", "records": 10, "selected_tables": ["patients"]},
    )
    assert response.status_code == 200
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    detail = client.get(f"/api/v1/runs/{job['run_id']}").json()
    generated_file = detail["generated_files"][0]

    preview = client.get(f"/api/v1/runs/{job['run_id']}/files/{generated_file['id']}/preview", params={"rows": 5})

    assert preview.status_code == 200
    payload = preview.json()
    assert payload["file_name"] == generated_file["file_name"]
    assert payload["row_count"] <= 5
    assert "patient_id" in payload["columns"]
    assert payload["rows"]
    assert "patient_id" in payload["rows"][0]


def test_generate_api_rejects_unknown_domain_before_queueing_job(client):
    response = client.post(
        "/api/v1/generate",
        json={"domain": "unknown", "load_type": "bulk", "format": "json", "records": 10},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "DATAFORGE_ERROR"
    assert response.json()["error"] == "Unsupported domain: unknown"


def test_generate_api_rejects_database_format_without_database_type(client):
    response = client.post(
        "/api/v1/generate",
        json={"domain": "retail", "load_type": "bulk", "format": "database", "records": 10, "selected_tables": ["categories"]},
    )
    assert response.status_code == 422


def test_generate_api_rejects_invalid_database_type(client):
    response = client.post(
        "/api/v1/generate",
        json={"domain": "retail", "load_type": "bulk", "format": "database", "database_type": "oracle", "records": 10, "selected_tables": ["categories"]},
    )
    assert response.status_code == 422


def test_generate_api_rejects_database_type_for_row_formats(client):
    response = client.post(
        "/api/v1/generate",
        json={"domain": "retail", "load_type": "bulk", "format": "csv", "database_type": "postgresql", "records": 10, "selected_tables": ["categories"]},
    )
    assert response.status_code == 422


def test_generate_api_supports_zero_row_dataset_zip_reports(client):
    response = client.post(
        "/api/v1/generate",
        json={"domain": "retail", "load_type": "bulk", "format": "csv", "records": 0, "selected_tables": ["sales"], "issues": {"null_values": 5}},
    )
    assert response.status_code == 200
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    assert job["status"] == "completed"
    run_id = job["run_id"]
    detail = client.get(f"/api/v1/runs/{run_id}").json()
    assert detail["record_count"] == 0
    assert detail["validation_results"][0]["quality_score"] == 100
    generated_file = detail["generated_files"][0]
    preview = client.get(f"/api/v1/runs/{run_id}/files/{generated_file['id']}/preview").json()
    assert preview["row_count"] == 0
    assert "sale_id" in preview["columns"]

    download = client.get(f"/api/v1/runs/{run_id}/download")
    assert download.status_code == 200
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        names = set(archive.namelist())
        assert "data/sales.csv" in names
        assert "reports/alignment_report.json" in names
        assert "reports/realism_report.json" in names
        validation_report = json.loads(archive.read("reports/validation_report.json"))
        alignment_report = json.loads(archive.read("reports/alignment_report.json"))
        realism_report = json.loads(archive.read("reports/realism_report.json"))
        assert validation_report["quality_score"] == 100
        assert alignment_report["status"] == "PASS"
        assert realism_report["no_public_rows_copied"] is True


def test_generate_api_supports_zero_row_database_ddl_package(client):
    response = client.post(
        "/api/v1/generate",
        json={"domain": "retail", "load_type": "bulk", "format": "database", "database_type": "postgresql", "records": 0, "selected_tables": ["sales"]},
    )
    assert response.status_code == 200
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    assert job["status"] == "completed"
    detail = client.get(f"/api/v1/runs/{job['run_id']}").json()
    assert detail["record_count"] == 0
    generated_file = detail["generated_files"][0]
    download = client.get(f"/api/v1/runs/{job['run_id']}/files/{generated_file['id']}/download")
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        assert "ddl/tables.sql" in archive.namelist()


def test_generate_api_persists_downloadable_database_ddl_zip(client):
    response = client.post(
        "/api/v1/generate",
        json={
            "domain": "ecommerce",
            "load_type": "bulk",
            "format": "database",
            "database_type": "postgresql",
            "records": 10,
            "selected_tables": ["marketplace_customers", "orders"],
        },
    )
    assert response.status_code == 200
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    assert job["status"] == "completed"
    detail = client.get(f"/api/v1/runs/{job['run_id']}").json()
    assert detail["format"] == "database"
    assert len(detail["generated_files"]) == 1
    generated_file = detail["generated_files"][0]
    assert generated_file["file_name"] == "ecommerce_postgresql_ddl.zip"
    assert generated_file["file_format"] == "database"
    assert generated_file["content_type"] == "application/zip"

    download = client.get(f"/api/v1/runs/{job['run_id']}/files/{generated_file['id']}/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/zip")
    assert b"ddl/schema.sql" in download.content
    assert b"ddl/foreign_keys.sql" in download.content


def test_catalog_tables_api_returns_domain_tables(client):
    response = client.get("/api/v1/catalog/tables/healthcare")
    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "healthcare"
    table_names = {table["name"] for table in payload["tables"]}
    assert {"patients", "visits", "claims", "payments"}.issubset(table_names)


def test_catalog_tables_api_returns_manufacturing_tables(client):
    response = client.get("/api/v1/catalog/tables/manufacturing")
    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "manufacturing"
    table_names = {table["name"] for table in payload["tables"]}
    assert {"factories", "production_lines", "work_orders", "production_batches", "quality_checks", "inventory"}.issubset(table_names)


def test_catalog_tables_api_returns_telecommunications_tables(client):
    response = client.get("/api/v1/catalog/tables/telecommunications")
    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "telecommunications"
    table_names = {table["name"] for table in payload["tables"]}
    assert {
        "telecom_customers",
        "subscriptions",
        "call_detail_records",
        "data_sessions",
        "network_events",
        "support_tickets",
    }.issubset(table_names)


def test_catalog_tables_api_returns_education_tables(client):
    response = client.get("/api/v1/catalog/tables/education")
    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "education"
    table_names = {table["name"] for table in payload["tables"]}
    assert {
        "institutions",
        "students",
        "enrollments",
        "attendance",
        "assignment_submissions",
        "examination_results",
        "fees_payments",
    }.issubset(table_names)


def test_catalog_tables_api_returns_ecommerce_tables(client):
    response = client.get("/api/v1/catalog/tables/ecommerce")
    assert response.status_code == 200
    payload = response.json()
    assert payload["domain"] == "ecommerce"
    table_names = {table["name"] for table in payload["tables"]}
    assert {
        "marketplace_customers",
        "sellers",
        "product_listings",
        "orders",
        "order_items",
        "payments",
        "shipments",
        "returns",
        "reviews",
    }.issubset(table_names)


def test_generate_api_supports_manufacturing_domain(client):
    response = client.post(
        "/api/v1/generate",
        json={"domain": "manufacturing", "load_type": "bulk", "format": "json", "records": 12, "selected_tables": ["work_orders", "production_batches"]},
    )
    assert response.status_code == 200
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    assert job["status"] == "completed"
    detail = client.get(f"/api/v1/runs/{job['run_id']}").json()
    assert detail["domain"] == "manufacturing"
    assert {file["file_name"] for file in detail["generated_files"]} == {"work_orders.json", "production_batches.json"}
    assert detail["validation_results"]


def test_generate_api_supports_telecommunications_domain(client):
    response = client.post(
        "/api/v1/generate",
        json={
            "domain": "telecommunications",
            "load_type": "bulk",
            "format": "json",
            "records": 12,
            "selected_tables": ["call_detail_records", "data_sessions"],
        },
    )
    assert response.status_code == 200
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    assert job["status"] == "completed"
    detail = client.get(f"/api/v1/runs/{job['run_id']}").json()
    assert detail["domain"] == "telecommunications"
    assert {file["file_name"] for file in detail["generated_files"]} == {"call_detail_records.json", "data_sessions.json"}
    assert detail["validation_results"]


def test_generate_api_supports_education_domain(client):
    response = client.post(
        "/api/v1/generate",
        json={
            "domain": "education",
            "load_type": "bulk",
            "format": "json",
            "records": 12,
            "selected_tables": ["enrollments", "fees_payments"],
        },
    )
    assert response.status_code == 200
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    assert job["status"] == "completed"
    detail = client.get(f"/api/v1/runs/{job['run_id']}").json()
    assert detail["domain"] == "education"
    assert {file["file_name"] for file in detail["generated_files"]} == {"enrollments.json", "fees_payments.json"}
    assert detail["validation_results"]


def test_generate_api_supports_ecommerce_domain(client):
    response = client.post(
        "/api/v1/generate",
        json={
            "domain": "ecommerce",
            "load_type": "bulk",
            "format": "json",
            "records": 12,
            "selected_tables": ["orders", "payments"],
        },
    )
    assert response.status_code == 200
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
    assert job["status"] == "completed"
    detail = client.get(f"/api/v1/runs/{job['run_id']}").json()
    assert detail["domain"] == "ecommerce"
    assert {file["file_name"] for file in detail["generated_files"]} == {"orders.json", "payments.json"}
    assert detail["validation_results"]


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

    job = client.get(f"/api/v1/jobs/{payload['job_id']}").json()
    detail = client.get(f"/api/v1/runs/{job['run_id']}").json()
    generated_names = {file["file_name"] for file in detail["generated_files"]}
    assert generated_names == {"customers.json", "deposit_accounts.json"}
    assert {issue["issue_type"] for issue in detail["issue_manifest"]}.intersection({"null_values", "duplicate_records"})


def test_job_status_endpoint_returns_completed_run_details(client):
    response = client.post(
        "/api/v1/generate",
        json={"domain": "retail", "load_type": "bulk", "format": "json", "records": 8, "selected_tables": ["customers"]},
    )
    job = client.get(f"/api/v1/jobs/{response.json()['job_id']}")
    assert job.status_code == 200
    payload = job.json()
    assert payload["status"] == "completed"
    assert payload["run_id"]
    assert payload["run"]["generated_files"]
    assert payload["run"]["validation_results"]
