from __future__ import annotations

from dataforge.domains.ecommerce.generators import EcommerceGenerator
from dataforge.domains.ecommerce.schemas import ECOMMERCE_SPEC
from dataforge.domains.education.generators import EducationGenerator
from dataforge.domains.education.schemas import EDUCATION_SPEC
from dataforge.domains.healthcare.generators import HealthcareGenerator
from dataforge.domains.healthcare.schemas import HEALTHCARE_SPEC
from dataforge.domains.manufacturing.generators import ManufacturingGenerator
from dataforge.domains.manufacturing.schemas import MANUFACTURING_SPEC
from dataforge.scenarios.catalog import expanded_scenario_items
from dataforge.scenarios.generic_executor import execute_generic_scenario
from dataforge.scenarios.requirements import REQUIREMENT_RESOLVER
from dataforge.validation import validate


def test_batch_7_new_domain_native_tables_generate_cleanly() -> None:
    ecommerce = EcommerceGenerator(100, seed=701).generate()
    assert ecommerce["seller_payouts"]
    assert validate(ecommerce, ECOMMERCE_SPEC)["overall_status"] == "PASS"
    assert {row["payout_status"] for row in ecommerce["seller_payouts"]} <= {"completed", "held", "failed", "pending"}

    education = EducationGenerator(100, seed=702).generate()
    assert education["academic_standing_events"]
    assert validate(education, EDUCATION_SPEC)["overall_status"] == "PASS"
    assert all(0 <= float(row["gpa"]) <= 4 for row in education["academic_standing_events"])

    healthcare = HealthcareGenerator(100, seed=703).generate()
    assert healthcare["prior_authorizations"]
    assert validate(healthcare, HEALTHCARE_SPEC)["overall_status"] == "PASS"
    assert {row["authorization_status"] for row in healthcare["prior_authorizations"]} <= {"Approved", "Denied", "Pending"}

    manufacturing = ManufacturingGenerator(100, seed=704).generate()
    assert manufacturing["sensor_readings"]
    assert validate(manufacturing, MANUFACTURING_SPEC)["overall_status"] == "PASS"
    assert {row["quality_flag"] for row in manufacturing["sensor_readings"]} <= {"normal", "warning", "critical"}


def test_batch_7_selected_table_generation_resolves_required_parent_tables() -> None:
    ecommerce = EcommerceGenerator(50, seed=711)
    ecommerce.selected_tables = {"seller_payouts"}
    ecommerce_data = ecommerce.generate()
    assert {"seller_payouts", "sellers", "seller_stores", "product_listings", "orders", "payments"} <= set(ecommerce_data)

    education = EducationGenerator(50, seed=712)
    education.selected_tables = {"academic_standing_events"}
    education_data = education.generate()
    assert {"academic_standing_events", "students", "academic_programs"} <= set(education_data)

    healthcare = HealthcareGenerator(50, seed=713)
    healthcare.selected_tables = {"prior_authorizations"}
    healthcare_data = healthcare.generate()
    assert {"prior_authorizations", "patients", "providers", "visits", "procedures"} <= set(healthcare_data)

    manufacturing = ManufacturingGenerator(50, seed=714)
    manufacturing.selected_tables = {"sensor_readings"}
    manufacturing_data = manufacturing.generate()
    assert {"sensor_readings", "factories", "production_lines", "machines"} <= set(manufacturing_data)


def test_batch_7_promoted_scenarios_execute_end_to_end() -> None:
    new_tables = {"seller_payouts", "academic_standing_events", "prior_authorizations", "sensor_readings"}
    scenarios = [
        item
        for item in expanded_scenario_items()
        if item.execution_status == "executable" and item.primary_table in new_tables
    ]
    assert len(scenarios) == 28
    assert {item.domain for item in scenarios} == {"ecommerce", "education", "healthcare", "manufacturing"}
    assert all(REQUIREMENT_RESOLVER.resolve(item).execution_supported for item in scenarios)

    for scenario in scenarios:
        result = execute_generic_scenario(scenario, records=80, seed=707)
        assert result.scenario_outcome == "PASS", scenario.scenario_id
        assert result.primitive_result["actual_mutated_count"] > 0, scenario.scenario_id
        assert result.validator_result["detected_count"] >= result.primitive_result["actual_mutated_count"], scenario.scenario_id
        assert result.validator_result["reconciliation_status"] == "PASS", scenario.scenario_id
        assert result.validator_result["evidence"], scenario.scenario_id
