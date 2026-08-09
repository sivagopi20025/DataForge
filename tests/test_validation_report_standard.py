from dataforge.domains.healthcare.generators import HealthcareGenerator
from dataforge.domains.healthcare.schemas import HEALTHCARE_SPEC
from dataforge.domains import DOMAIN_SPECS
from dataforge.reporting import quality_score, quality_score_details
from dataforge.validation import validate


def test_validation_report_has_standard_contract_for_every_domain():
    required = {
        "run_id",
        "domain",
        "load_type",
        "format",
        "record_count",
        "quality_score",
        "status",
        "summary",
        "issues",
        "checks",
        "generated_at",
    }
    for domain, spec in DOMAIN_SPECS.items():
        assert required <= set(validate({}, spec, selected_tables=set()) | {"checks": []})


def test_validation_report_includes_score_and_standardized_checks():
    data = HealthcareGenerator(20, seed=101).generate()
    report = validate(data, HEALTHCARE_SPEC, run_id="run-1", load_type="bulk", file_format="json", record_count=20)
    assert report["run_id"] == "run-1"
    assert report["domain"] == "healthcare"
    assert report["load_type"] == "bulk"
    assert report["format"] == "json"
    assert report["record_count"] == 20
    assert 0 <= report["quality_score"] <= 100
    assert report["summary"]["total_checks"] == len(report["checks"])
    assert {"name", "status", "expected", "actual"} <= set(report["checks"][0])
    assert "scoring" in report
    assert report["scoring"]["score"] == report["quality_score"]


def test_quality_score_is_proportional_for_small_row_level_failures():
    data = {"orders": [{"order_id": index} for index in range(100)]}
    checks = [
        {"check": "primary_key_unique", "table": "orders", "failures": 0, "status": "PASS"},
        {"check": "referential_integrity", "table": "orders", "failures": 1, "status": "FAIL"},
        {"check": "not_null", "table": "orders", "failures": 1, "status": "FAIL"},
        {"check": "valid_datetime", "table": "orders", "failures": 0, "status": "PASS"},
    ]

    score = quality_score(checks, data=data)
    details = quality_score_details(checks, data=data)

    assert 95 <= score <= 100
    assert details["categories"]["fk"]["impact"] == 0.01
    assert details["categories"]["schema"]["impact"] == 0.01


def test_quality_score_penalizes_table_level_schema_failures_strongly():
    data = {"orders": [{"order_id": index} for index in range(100)]}
    checks = [
        {"check": "primary_key_unique", "table": "orders", "failures": 0, "status": "PASS"},
        {"check": "schema_columns_match", "table": "orders", "failures": 1, "status": "FAIL"},
    ]

    score = quality_score(checks, data=data)
    details = quality_score_details(checks, data=data)

    assert score == 80
    assert details["categories"]["schema"]["impact"] == 1.0


def test_quality_score_reaches_zero_for_severe_full_category_failures():
    data = {"orders": [{"order_id": index} for index in range(10)]}
    checks = [
        {"check": "primary_key_unique", "table": "orders", "failures": 10, "status": "FAIL"},
        {"check": "referential_integrity", "table": "orders", "failures": 10, "status": "FAIL"},
        {"check": "schema_columns_match", "table": "orders", "failures": 1, "status": "FAIL"},
        {"check": "duplicate_records", "table": "orders", "failures": 10, "status": "FAIL"},
        {"check": "valid_datetime", "table": "orders", "failures": 10, "status": "FAIL"},
        {"check": "business_rule", "table": "orders", "failures": 10, "status": "FAIL"},
    ]

    assert quality_score(checks, data=data) == 0
