from __future__ import annotations

import copy
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from dataforge.domains.ecommerce.generators import EcommerceGenerator
from dataforge.domains.ecommerce.schemas import ECOMMERCE_SPEC
from dataforge.domains.education.generators import EducationGenerator
from dataforge.domains.education.schemas import EDUCATION_SPEC
from dataforge.domains.banking.generators import BankingGenerator
from dataforge.domains.banking.schemas import BANKING_SPEC
from dataforge.domains.finance.generators import FinanceGenerator
from dataforge.domains.finance.schemas import FINANCE_SPEC
from dataforge.domains.healthcare.generators import HealthcareGenerator
from dataforge.domains.healthcare.schemas import HEALTHCARE_SPEC
from dataforge.domains.insurance.generators import InsuranceGenerator
from dataforge.domains.insurance.schemas import INSURANCE_SPEC
from dataforge.domains.logistics.generators import LogisticsGenerator
from dataforge.domains.logistics.schemas import LOGISTICS_SPEC
from dataforge.domains.manufacturing.generators import ManufacturingGenerator
from dataforge.domains.manufacturing.schemas import MANUFACTURING_SPEC
from dataforge.domains.retail.generators import RetailGenerator
from dataforge.domains.retail.schemas import RETAIL_SPEC
from dataforge.domains.telecommunications.generators import TelecommunicationsGenerator
from dataforge.domains.telecommunications.schemas import TELECOMMUNICATIONS_SPEC
from dataforge.injector import FailureInjector
from dataforge.realism import (
    BANKING_PROFILES,
    ECOMMERCE_SOURCE_RATIOS,
    EDUCATION_PROFILES,
    FINANCE_PROFILES,
    HEALTHCARE_PROFILES,
    INSURANCE_PROFILES,
    LOGISTICS_PROFILES,
    RETAIL_BUSINESS_PROFILES,
    TELECOM_PROFILES,
    apply_realism,
)
from dataforge.validation import validate

REALISM_CONTRACT_KEYS = {
    "realism_profile",
    "profile_description",
    "primary_transaction_table",
    "expected_metrics",
    "actual_metrics",
    "tolerance",
    "deviation",
    "sample_size",
    "statistical_stability",
    "warnings",
    "overall_realism_status",
    "calibration_disclaimer",
    "source_references",
    "no_copied_rows_statement",
}


def _retail(records: int = 500, seed: int = 42):
    return RetailGenerator(records, seed).generate(), RETAIL_SPEC


def _ecommerce(records: int = 500, seed: int = 42):
    return EcommerceGenerator(records, seed).generate(), ECOMMERCE_SPEC


def _manufacturing(records: int = 500, seed: int = 42):
    return ManufacturingGenerator(records, seed).generate(), MANUFACTURING_SPEC


def _banking(records: int = 500, seed: int = 42):
    return BankingGenerator(records, seed).generate(), BANKING_SPEC


def _healthcare(records: int = 500, seed: int = 42):
    return HealthcareGenerator(records, seed).generate(), HEALTHCARE_SPEC


def _telecom(records: int = 500, seed: int = 42):
    return TelecommunicationsGenerator(records, seed).generate(), TELECOMMUNICATIONS_SPEC


def _logistics(records: int = 500, seed: int = 42):
    return LogisticsGenerator(records, seed).generate(), LOGISTICS_SPEC


def _insurance(records: int = 500, seed: int = 42):
    return InsuranceGenerator(records, seed).generate(), INSURANCE_SPEC


def _finance(records: int = 500, seed: int = 42):
    return FinanceGenerator(records, seed).generate(), FINANCE_SPEC


def _education(records: int = 500, seed: int = 42):
    return EducationGenerator(records, seed).generate(), EDUCATION_SPEC


def test_realism_same_seed_is_reproducible_for_supported_domains() -> None:
    for build in (_retail, _ecommerce, _manufacturing, _banking, _healthcare, _telecom, _logistics, _insurance, _finance, _education):
        data, spec = build(250, 91)
        first, first_report = apply_realism(data, spec, seed=91)
        second, second_report = apply_realism(copy.deepcopy(data), spec, seed=91)
        assert first == second
        assert first_report["distribution_summary"] == second_report["distribution_summary"]


def test_all_domains_emit_shared_realism_report_contract() -> None:
    for build in (_retail, _ecommerce, _manufacturing, _banking, _healthcare, _telecom, _logistics, _insurance, _finance, _education):
        data, spec = build(350, 42)
        _, report = apply_realism(data, spec, seed=42)
        assert REALISM_CONTRACT_KEYS <= set(report)
        assert report["realism_profile"]
        assert report["profile_description"]
        assert report["primary_transaction_table"] in spec.schemas
        assert isinstance(report["expected_metrics"], dict)
        assert isinstance(report["actual_metrics"], dict)
        assert isinstance(report["tolerance"], dict)
        assert isinstance(report["deviation"], dict)
        assert report["sample_size"] == len(data[report["primary_transaction_table"]])
        assert report["statistical_stability"] in {"STABLE", "LOW_SAMPLE", "LOW_SAMPLE_WARNING", "EMPTY_SCHEMA_ONLY"}
        assert report["overall_realism_status"] == "PASS"
        assert report["calibration_disclaimer"]
        assert report["source_references"]
        assert all(source["no_copied_rows"] for source in report["source_references"])
        assert report["no_public_rows_copied"] is True
        assert "not copied" in report["no_copied_rows_statement"]


def test_small_sample_realism_reports_statistical_stability_warning() -> None:
    data, spec = _retail(50, 42)
    _, report = apply_realism(data, spec, seed=42)
    assert report["sample_size"] == 50
    assert report["statistical_stability"] in {"LOW_SAMPLE", "LOW_SAMPLE_WARNING"}


def test_realism_different_seed_changes_generated_patterns() -> None:
    data, spec = _retail(250, 13)
    first, _ = apply_realism(data, spec, seed=13)
    second, _ = apply_realism(copy.deepcopy(data), spec, seed=14)
    first_signature = [(row["customer_id"], row["product_id"], row["sale_timestamp"]) for row in first["sales"][:25]]
    second_signature = [(row["customer_id"], row["product_id"], row["sale_timestamp"]) for row in second["sales"][:25]]
    assert first_signature != second_signature


def test_telecom_and_logistics_different_seed_variation() -> None:
    for build, table, fields in (
        (_telecom, "data_sessions", ("tower_id", "session_start_time", "data_used_mb")),
        (_logistics, "shipments", ("shipment_type", "shipment_status", "created_at")),
    ):
        data, spec = build(400, 23)
        first, _ = apply_realism(data, spec, seed=23)
        second, _ = apply_realism(copy.deepcopy(data), spec, seed=24)
        assert [tuple(row[field] for field in fields) for row in first[table][:30]] != [tuple(row[field] for field in fields) for row in second[table][:30]]


def test_insurance_finance_and_education_different_seed_variation() -> None:
    for build, table, fields in (
        (_insurance, "claims", ("policy_id", "claim_amount", "claim_date")),
        (_finance, "transactions", ("account_id", "transaction_amount", "transaction_timestamp")),
        (_education, "enrollments", ("final_grade", "completion_status", "enrollment_status")),
    ):
        data, spec = build(500, 31)
        first, _ = apply_realism(data, spec, seed=31)
        second, _ = apply_realism(copy.deepcopy(data), spec, seed=32)
        assert [tuple(row[field] for field in fields) for row in first[table][:40]] != [tuple(row[field] for field in fields) for row in second[table][:40]]


def test_realistic_profile_differs_from_basic_profile() -> None:
    data, spec = _retail(250, 42)
    basic, basic_report = apply_realism(data, spec, profile="basic", seed=42)
    realistic, realistic_report = apply_realism(copy.deepcopy(data), spec, profile="realistic", seed=42)
    assert basic_report["status"] == "SKIPPED"
    assert realistic_report["status"] == "PASS"
    assert basic["sales"][0]["sale_timestamp"] != realistic["sales"][0]["sale_timestamp"]


def test_stress_profile_increases_retail_evening_peak() -> None:
    data, spec = _retail(500, 42)
    _, realistic_report = apply_realism(data, spec, profile="realistic", seed=42)
    _, stress_report = apply_realism(copy.deepcopy(data), spec, profile="stress", seed=42)
    assert stress_report["distribution_summary"]["evening_sales_share"] >= realistic_report["distribution_summary"]["evening_sales_share"]


def test_retail_business_profiles_have_calibrated_temporal_ranges() -> None:
    data, spec = _retail(1_000, 42)
    for profile, config in RETAIL_BUSINESS_PROFILES.items():
        _, report = apply_realism(copy.deepcopy(data), spec, profile=profile, seed=42)
        lower, upper = config["evening_sales_share_range"]
        actual = report["actual_metrics"]["retail_evening_sales_share"]
        assert lower - 0.05 <= actual <= upper + 0.05
        assert report["distribution_summary"]["business_profile"] == profile
        assert report["overall_realism_status"] == "PASS"


def test_retail_customer_segment_and_product_skew() -> None:
    data, spec = _retail(600, 42)
    realistic, report = apply_realism(data, spec, seed=42)
    customer_segment = {row["customer_id"]: row["loyalty_level"] for row in realistic["customers"]}
    amounts: dict[str, list[Decimal]] = defaultdict(list)
    for sale in realistic["sales"]:
        amounts[customer_segment[sale["customer_id"]]].append(Decimal(str(sale["sale_amount"])))
    bronze_avg = sum(amounts["BRONZE"], Decimal("0")) / len(amounts["BRONZE"])
    platinum_avg = sum(amounts["PLATINUM"], Decimal("0")) / len(amounts["PLATINUM"])
    assert platinum_avg > bronze_avg
    assert len(report["distribution_summary"]["sales_by_category"]) >= 3


def test_ecommerce_funnel_ratios_and_payment_reconciliation() -> None:
    data, spec = _ecommerce(500, 42)
    realistic, report = apply_realism(data, spec, seed=42)
    counts = report["distribution_summary"]["funnel_counts"]
    assert counts["estimated_product_views"] > counts["carts"] > counts["cart_sourced_orders"]
    assert counts["returns"] <= counts["shipments"] <= counts["orders"]
    assert counts["payment_attempts"] == counts["orders"]
    assert counts["successful_payments"] < counts["payment_attempts"]
    totals = {row["order_id"]: Decimal(str(row["total_amount"])) for row in realistic["orders"]}
    for payment in realistic["payments"]:
        if payment["payment_status"] == "successful":
            assert Decimal(str(payment["payment_amount"])) == totals[payment["order_id"]]


def test_ecommerce_orders_have_documented_mixed_sources() -> None:
    data, spec = _ecommerce(2_000, 42)
    realistic, report = apply_realism(data, spec, seed=42)
    actual_sources = {row["order_source"] for row in realistic["orders"]}
    assert set(ECOMMERCE_SOURCE_RATIOS) == actual_sources
    for source, expected_ratio in ECOMMERCE_SOURCE_RATIOS.items():
        assert abs(report["actual_metrics"]["order_source_ratios"][source] - expected_ratio) <= 0.06
    assert report["expected_metrics"]["estimated_product_views_gt_carts_gt_cart_sourced_orders"] is True


def test_banking_profiles_differentiate_balance_and_payment_patterns() -> None:
    data, spec = _banking(1_000, 42)
    retail, retail_report = apply_realism(data, spec, profile="retail_consumer", seed=42)
    commercial, commercial_report = apply_realism(data, spec, profile="commercial", seed=42)
    assert set(BANKING_PROFILES) >= {"retail_consumer", "small_business", "commercial", "digital_bank", "high_net_worth"}
    assert commercial_report["actual_metrics"]["average_commercial_payment"] > retail_report["actual_metrics"]["average_commercial_payment"]
    retail_avg_balance = sum(Decimal(str(row["balance"])) for row in retail["deposit_accounts"]) / len(retail["deposit_accounts"])
    commercial_avg_balance = sum(Decimal(str(row["balance"])) for row in commercial["deposit_accounts"]) / len(commercial["deposit_accounts"])
    assert commercial_avg_balance > retail_avg_balance


def test_banking_balance_reconciliation_and_balanced_ledger() -> None:
    data, spec = _banking(1_200, 42)
    realistic, report = apply_realism(data, spec, profile="small_business", seed=42)
    validation = validate(realistic, spec)
    assert validation["quality_score"] == 100
    assert report["actual_metrics"]["ledger_difference"] <= 0.01
    assert report["actual_metrics"]["completed_transfer_count"] > 0
    assert report["actual_metrics"]["average_commercial_payment"] > report["actual_metrics"]["average_consumer_payment"]


def test_banking_payroll_cluster_and_high_value_rarity_across_seeds() -> None:
    for seed in (17, 42, 88):
        data, spec = _banking(1_500, seed)
        _, report = apply_realism(data, spec, profile="digital_bank", seed=seed)
        assert report["overall_realism_status"] == "PASS"
        assert abs(report["actual_metrics"]["payroll_payment_share"] - BANKING_PROFILES["digital_bank"]["payroll_share"]) <= 0.08
        assert report["actual_metrics"]["high_value_payment_share"] <= 0.06


def test_healthcare_profiles_differentiate_inpatient_rate_and_approval() -> None:
    data, spec = _healthcare(1_000, 42)
    outpatient, outpatient_report = apply_realism(data, spec, profile="outpatient_clinic", seed=42)
    emergency, emergency_report = apply_realism(data, spec, profile="emergency_care", seed=42)
    assert set(HEALTHCARE_PROFILES) >= {"primary_care", "hospital_network", "outpatient_clinic", "chronic_care", "emergency_care"}
    assert emergency_report["actual_metrics"]["inpatient_rate"] > outpatient_report["actual_metrics"]["inpatient_rate"]
    assert validate(outpatient, spec)["quality_score"] == 100
    assert validate(emergency, spec)["quality_score"] == 100


def test_healthcare_age_condition_and_cost_correlations_across_seeds() -> None:
    for seed in (21, 42, 111):
        data, spec = _healthcare(1_200, seed)
        _, report = apply_realism(data, spec, profile="chronic_care", seed=seed)
        assert report["overall_realism_status"] == "PASS"
        assert report["actual_metrics"]["chronic_rate_age_60_plus"] > report["actual_metrics"]["chronic_rate_under_40"]
        assert report["actual_metrics"]["average_inpatient_procedure_cost"] > report["actual_metrics"]["average_outpatient_procedure_cost"]
        assert report["actual_metrics"]["average_chronic_patient_visits"] > report["actual_metrics"]["average_non_chronic_patient_visits"]


def test_healthcare_diagnosis_procedure_compatibility_and_date_sequence() -> None:
    data, spec = _healthcare(800, 42)
    realistic, _ = apply_realism(data, spec, profile="hospital_network", seed=42)
    diagnosis_by_visit = {row["visit_id"]: row["icd10_code"] for row in realistic["diagnoses"]}
    procedure_by_visit = {row["visit_id"]: row["cpt_code"] for row in realistic["procedures"]}
    compatible = {
        "I10": "99213",
        "E11.9": "80053",
        "J06.9": "99213",
        "M54.5": "97110",
        "R07.9": "93000",
        "G43.909": "70450",
    }
    for visit_id, diagnosis in diagnosis_by_visit.items():
        assert procedure_by_visit[visit_id] == compatible[diagnosis]
    visits = {row["visit_id"]: datetime.fromisoformat(row["visit_date"]) for row in realistic["visits"]}
    claims = {row["claim_id"]: row for row in realistic["claims"]}
    for claim in realistic["claims"]:
        assert datetime.fromisoformat(claim["submitted_date"]) >= visits[claim["visit_id"]]
    for payment in realistic["payments"]:
        assert datetime.fromisoformat(payment["payment_date"]) >= datetime.fromisoformat(claims[payment["claim_id"]]["submitted_date"])


def test_telecom_profiles_and_usage_correlations() -> None:
    data, spec = _telecom(1_200, 42)
    urban, urban_report = apply_realism(data, spec, profile="urban_consumer", seed=42)
    rural, rural_report = apply_realism(copy.deepcopy(data), spec, profile="rural_consumer", seed=42)
    enterprise, enterprise_report = apply_realism(copy.deepcopy(data), spec, profile="enterprise", seed=42)
    assert set(TELECOM_PROFILES) >= {"urban_consumer", "suburban_consumer", "rural_consumer", "business", "enterprise", "iot_fleet"}
    assert rural_report["actual_metrics"]["rural_drop_rate"] > urban_report["actual_metrics"]["urban_drop_rate"]
    assert enterprise_report["actual_metrics"]["average_5g_data_mb"] > 0
    assert validate(urban, spec)["quality_score"] == 100
    assert validate(rural, spec)["quality_score"] == 100


def test_telecom_evening_5g_rural_congestion_and_invoice_reconciliation_across_seeds() -> None:
    for seed in (7, 42, 99):
        data, spec = _telecom(1_200, seed)
        realistic, report = apply_realism(data, spec, profile="urban_consumer", seed=seed)
        assert report["overall_realism_status"] == "PASS"
        assert report["actual_metrics"]["average_5g_data_mb"] > report["actual_metrics"]["average_4g_lte_data_mb"]
        assert report["actual_metrics"]["rural_drop_rate"] > report["actual_metrics"]["urban_drop_rate"]
        assert report["actual_metrics"]["congested_failure_rate"] > report["actual_metrics"]["normal_failure_rate"]
        assert report["actual_metrics"]["invoice_reconciliation_difference"] <= 0.05
        assert validate(realistic, spec)["quality_score"] == 100


def test_logistics_profiles_and_distance_delivery_correlations() -> None:
    data, spec = _logistics(1_000, 42)
    express, express_report = apply_realism(data, spec, profile="express", seed=42)
    freight, freight_report = apply_realism(copy.deepcopy(data), spec, profile="freight", seed=42)
    assert set(LOGISTICS_PROFILES) >= {"urban_last_mile", "national_ground", "international_air", "cold_chain", "express", "freight"}
    assert express_report["actual_metrics"]["delivered_share"] >= freight_report["actual_metrics"]["delivered_share"] - 0.15
    assert express_report["actual_metrics"]["average_express_cost"] > express_report["actual_metrics"]["average_standard_cost"]
    assert express_report["actual_metrics"]["average_express_duration_hours"] < express_report["actual_metrics"]["average_standard_duration_hours"]
    assert validate(express, spec)["quality_score"] == 100


def test_logistics_status_sequence_cold_chain_and_distance_stability_across_seeds() -> None:
    for seed in (13, 42, 77):
        data, spec = _logistics(1_200, seed)
        realistic, report = apply_realism(data, spec, profile="cold_chain", seed=seed)
        validation = validate(realistic, spec)
        assert report["overall_realism_status"] == "PASS"
        assert validation["quality_score"] == 100
        assert report["actual_metrics"]["average_long_distance_duration_hours"] > report["actual_metrics"]["average_short_distance_duration_hours"]
        assert report["actual_metrics"]["cold_chain_compliance"] >= 0.85
        assert report["distribution_summary"]["tracking_event_counts"]["created"] == len(realistic["shipments"])


def test_insurance_profiles_and_risk_correlations() -> None:
    data, spec = _insurance(1_000, 42)
    personal, personal_report = apply_realism(data, spec, profile="personal_auto", seed=42)
    high_risk, high_risk_report = apply_realism(copy.deepcopy(data), spec, profile="high_risk", seed=42)
    assert set(INSURANCE_PROFILES) >= {"personal_auto", "homeowners", "health_supplemental", "commercial", "life", "high_risk"}
    assert personal_report["overall_realism_status"] == "PASS"
    assert high_risk_report["overall_realism_status"] == "PASS"
    assert high_risk_report["actual_metrics"]["average_high_risk_premium"] > personal_report["actual_metrics"]["average_normal_risk_premium"]
    assert high_risk_report["actual_metrics"]["high_risk_claim_share"] > high_risk_report["actual_metrics"]["normal_claim_share"]
    assert validate(personal, spec)["quality_score"] == 100
    assert validate(high_risk, spec)["quality_score"] == 100


def test_insurance_claim_coverage_deductible_and_rare_suspicious_claims_across_seeds() -> None:
    for seed in (19, 42, 101):
        data, spec = _insurance(1_200, seed)
        realistic, report = apply_realism(data, spec, profile="commercial", seed=seed)
        policies = {row["policy_id"]: Decimal(str(row["coverage_amount"])) for row in realistic["policies"]}
        claims = {row["claim_id"]: row for row in realistic["claims"]}
        for claim in realistic["claims"]:
            assert Decimal(str(claim["claim_amount"])) <= policies[claim["policy_id"]]
        for settlement in realistic["settlements"]:
            assert Decimal(str(settlement["settlement_amount"])) <= Decimal(str(claims[settlement["claim_id"]]["claim_amount"]))
        assert report["overall_realism_status"] == "PASS"
        assert report["actual_metrics"]["suspicious_claim_rate"] <= 0.08
        assert report["actual_metrics"]["average_deductible_effect"] > 0
        assert validate(realistic, spec)["quality_score"] == 100


def test_finance_profiles_trade_size_business_hours_and_fee_reconciliation() -> None:
    data, spec = _finance(1_200, 42)
    conservative, conservative_report = apply_realism(data, spec, profile="conservative", seed=42)
    institutional, institutional_report = apply_realism(copy.deepcopy(data), spec, profile="institutional", seed=42)
    assert set(FINANCE_PROFILES) >= {"retail_investing", "institutional", "treasury", "wealth_management", "high_frequency", "conservative"}
    assert institutional_report["actual_metrics"]["average_business_trade"] > conservative_report["actual_metrics"]["average_business_trade"]
    assert institutional_report["actual_metrics"]["average_business_trade"] > institutional_report["actual_metrics"]["average_retail_trade"]
    assert 0.0012 <= institutional_report["actual_metrics"]["modeled_fee_rate"] <= 0.0018
    assert validate(conservative, spec)["quality_score"] == 100
    assert validate(institutional, spec)["quality_score"] == 100


def test_finance_high_value_rarity_business_hour_and_month_end_across_seeds() -> None:
    for seed in (13, 42, 90):
        data, spec = _finance(1_500, seed)
        realistic, report = apply_realism(data, spec, profile="high_frequency", seed=seed)
        lower, upper = FINANCE_PROFILES["high_frequency"]["business_hour_share"]
        assert report["overall_realism_status"] == "PASS"
        assert lower - 0.08 <= report["actual_metrics"]["business_hour_share"] <= upper + 0.08
        assert report["actual_metrics"]["high_value_trade_share"] <= 0.08
        assert report["actual_metrics"]["month_end_activity_share"] >= 0.15
        assert validate(realistic, spec)["quality_score"] == 100


def test_education_profiles_attendance_grade_capacity_and_online_behavior() -> None:
    data, spec = _education(1_000, 42)
    k12, k12_report = apply_realism(data, spec, profile="K12", seed=42)
    online, online_report = apply_realism(copy.deepcopy(data), spec, profile="online_learning", seed=42)
    assert set(EDUCATION_PROFILES) >= {"K12", "community_college", "university", "online_learning", "vocational", "graduate_school"}
    assert k12_report["actual_metrics"]["average_section_capacity"] < online_report["actual_metrics"]["average_section_capacity"]
    assert k12_report["actual_metrics"]["average_high_attendance_grade"] > k12_report["actual_metrics"]["average_low_attendance_grade"]
    assert online_report["distribution_summary"]["education_profile"] == "online_learning"
    assert validate(k12, spec)["quality_score"] == 100
    assert validate(online, spec)["quality_score"] == 100


def test_education_late_submissions_fee_holds_dates_and_multi_seed_stability() -> None:
    for seed in (17, 42, 103):
        data, spec = _education(1_200, seed)
        realistic, report = apply_realism(data, spec, profile="community_college", seed=seed)
        assignments = {row["assignment_id"]: row for row in realistic["assignments"]}
        for submission in realistic["assignment_submissions"]:
            assignment = assignments[submission["assignment_id"]]
            assert datetime.fromisoformat(submission["submission_date"]) >= datetime.fromisoformat(assignment["assigned_date"])
            assert Decimal(str(submission["marks_obtained"])) <= Decimal(str(assignment["maximum_marks"]))
        assert report["overall_realism_status"] == "PASS"
        assert report["actual_metrics"]["late_submission_rate"] >= 0.05
        assert 0 <= report["actual_metrics"]["registration_hold_share"] <= 0.25
        assert validate(realistic, spec)["quality_score"] == 100


def test_manufacturing_machine_age_and_downtime_relationship() -> None:
    data, spec = _manufacturing(500, 42)
    _, report = apply_realism(data, spec, seed=42)
    summary = report["distribution_summary"]
    assert Decimal(summary["average_downtime_old_machines"]) > Decimal(summary["average_downtime_new_machines"])
    assert Decimal(summary["average_reject_rate_night"]) > Decimal(summary["average_reject_rate_day"])


def test_manufacturing_correlations_hold_across_multiple_larger_seeded_runs() -> None:
    for seed in (11, 42, 91, 123):
        data, spec = _manufacturing(1_200, seed)
        _, report = apply_realism(data, spec, seed=seed)
        assert report["overall_realism_status"] == "PASS"
        assert report["actual_metrics"]["older_machine_downtime_lift_minutes"] >= 2.0
        assert report["actual_metrics"]["night_shift_reject_rate_lift"] >= 0.008


def test_primary_record_count_controls_table_volume_ratios() -> None:
    retail, _ = _retail(300, 42)
    ecommerce, _ = _ecommerce(300, 42)
    manufacturing, _ = _manufacturing(300, 42)
    assert len(retail["sales"]) == 300
    assert len(retail["customers"]) < len(retail["sales"])
    assert len(ecommerce["orders"]) == 300
    assert len(ecommerce["order_items"]) > len(ecommerce["orders"])
    assert len(manufacturing["work_orders"]) == 300
    assert len(manufacturing["production_batches"]) > len(manufacturing["work_orders"])


def test_realistic_clean_data_keeps_quality_score_100() -> None:
    for build in (_retail, _ecommerce, _manufacturing, _banking, _healthcare, _telecom, _logistics, _insurance, _finance, _education):
        data, spec = build(250, 42)
        realistic, report = apply_realism(data, spec, seed=42)
        validation = validate(realistic, spec)
        assert report["status"] == "PASS"
        assert validation["quality_score"] == 100
        assert validation["summary"]["failed"] == 0


def test_failure_injection_still_detects_issues_after_realism() -> None:
    data, spec = _retail(300, 42)
    realistic, _ = apply_realism(data, spec, seed=42)
    injected, events = FailureInjector({"null_values": 0.02, "foreign_key_break": 0.02}, seed=42, spec=spec).apply(realistic)
    validation = validate(injected, spec)
    assert events
    assert validation["summary"]["failed"] > 0
    assert validation["quality_score"] < 100


def test_banking_and_healthcare_failure_injection_still_works_after_realism() -> None:
    for build in (_banking, _healthcare):
        data, spec = build(400, 42)
        realistic, _ = apply_realism(data, spec, seed=42)
        injected, events = FailureInjector({"null_values": 0.02, "foreign_key_break": 0.02}, seed=42, spec=spec).apply(realistic)
        validation = validate(injected, spec)
        assert events
        assert validation["quality_score"] < 100


def test_telecom_and_logistics_failure_injection_still_works_after_realism() -> None:
    for build in (_telecom, _logistics):
        data, spec = build(400, 42)
        realistic, _ = apply_realism(data, spec, seed=42)
        injected, events = FailureInjector({"null_values": 0.02, "foreign_key_break": 0.02}, seed=42, spec=spec).apply(realistic)
        validation = validate(injected, spec)
        assert events
        assert validation["quality_score"] < 100


def test_insurance_finance_and_education_failure_injection_still_works_after_realism() -> None:
    for build in (_insurance, _finance, _education):
        data, spec = build(400, 42)
        realistic, _ = apply_realism(data, spec, seed=42)
        injected, events = FailureInjector({"null_values": 0.02, "foreign_key_break": 0.02}, seed=42, spec=spec).apply(realistic)
        validation = validate(injected, spec)
        assert events
        assert validation["quality_score"] < 100


def test_ecommerce_temporal_sequence_is_valid() -> None:
    data, spec = _ecommerce(300, 42)
    realistic, _ = apply_realism(data, spec, seed=42)
    orders = {row["order_id"]: datetime.fromisoformat(row["order_date"]) for row in realistic["orders"]}
    for payment in realistic["payments"]:
        assert datetime.fromisoformat(payment["payment_date"]) > orders[payment["order_id"]]
    for shipment in realistic["shipments"]:
        assert datetime.fromisoformat(shipment["delivered_at"]) > datetime.fromisoformat(shipment["shipped_at"])
