from dataforge.domains.healthcare.generators import HealthcareGenerator
from dataforge.domains.healthcare.schemas import HEALTHCARE_SPEC
from dataforge.domains import DOMAIN_SPECS
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
