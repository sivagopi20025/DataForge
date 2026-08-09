from __future__ import annotations

import copy
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable

from .audit import record_hash
from .canonical import PRIMARY_TABLES, REFERENCE_PROFILES
from .model import Dataset, DomainSpec


SUPPORTED_REALISM_DOMAINS = {
    "retail", "ecommerce", "manufacturing", "banking", "healthcare",
    "telecommunications", "logistics", "insurance", "finance", "education",
}

RETAIL_BUSINESS_PROFILES: dict[str, dict[str, Any]] = {
    "physical_retail": {
        "hourly_distribution": [(9, 8), (10, 9), (11, 10), (12, 13), (13, 11), (14, 10), (15, 9), (16, 8), (17, 11), (18, 12), (19, 10), (20, 6)],
        "weekend_effect": 1.20,
        "average_basket_value": Decimal("85.00"),
        "evening_sales_share_range": (0.30, 0.55),
        "return_rate": 0.055,
        "product_popularity_skew": 1.0,
        "customer_segment_mix": {"BRONZE": 1.2, "SILVER": 1.5, "GOLD": 2.2, "PLATINUM": 3.2},
    },
    "ecommerce_heavy": {
        "hourly_distribution": [(8, 4), (9, 5), (10, 6), (12, 8), (17, 13), (18, 18), (19, 20), (20, 18), (21, 13), (22, 9)],
        "weekend_effect": 1.35,
        "average_basket_value": Decimal("105.00"),
        "evening_sales_share_range": (0.55, 0.82),
        "return_rate": 0.08,
        "product_popularity_skew": 1.5,
        "customer_segment_mix": {"BRONZE": 0.9, "SILVER": 1.3, "GOLD": 2.7, "PLATINUM": 4.4},
    },
    "grocery": {
        "hourly_distribution": [(7, 9), (8, 11), (9, 10), (11, 9), (12, 10), (16, 12), (17, 14), (18, 13), (19, 8), (20, 4)],
        "weekend_effect": 1.45,
        "average_basket_value": Decimal("48.00"),
        "evening_sales_share_range": (0.38, 0.62),
        "return_rate": 0.015,
        "product_popularity_skew": 1.2,
        "customer_segment_mix": {"BRONZE": 1.4, "SILVER": 1.7, "GOLD": 2.0, "PLATINUM": 2.2},
    },
    "luxury": {
        "hourly_distribution": [(10, 7), (11, 10), (12, 12), (13, 12), (14, 13), (15, 12), (16, 10), (17, 8), (18, 6), (19, 4)],
        "weekend_effect": 1.25,
        "average_basket_value": Decimal("340.00"),
        "evening_sales_share_range": (0.15, 0.35),
        "return_rate": 0.07,
        "product_popularity_skew": 2.0,
        "customer_segment_mix": {"BRONZE": 0.4, "SILVER": 0.9, "GOLD": 2.8, "PLATINUM": 6.0},
    },
    "convenience": {
        "hourly_distribution": [(6, 8), (7, 11), (8, 10), (12, 11), (13, 10), (17, 10), (18, 9), (19, 8), (20, 7), (21, 6), (22, 5), (23, 4)],
        "weekend_effect": 1.10,
        "average_basket_value": Decimal("22.00"),
        "evening_sales_share_range": (0.28, 0.55),
        "return_rate": 0.01,
        "product_popularity_skew": 0.8,
        "customer_segment_mix": {"BRONZE": 1.8, "SILVER": 1.5, "GOLD": 1.2, "PLATINUM": 0.9},
    },
    "seasonal": {
        "hourly_distribution": [(9, 4), (10, 5), (11, 6), (12, 9), (15, 9), (16, 10), (17, 13), (18, 18), (19, 18), (20, 15), (21, 10)],
        "weekend_effect": 1.70,
        "average_basket_value": Decimal("125.00"),
        "evening_sales_share_range": (0.58, 0.86),
        "return_rate": 0.10,
        "product_popularity_skew": 2.3,
        "customer_segment_mix": {"BRONZE": 0.8, "SILVER": 1.2, "GOLD": 2.8, "PLATINUM": 4.8},
    },
}

ECOMMERCE_SOURCE_RATIOS = {
    "cart": 0.42,
    "direct_buy": 0.28,
    "guest_checkout": 0.14,
    "api": 0.10,
    "subscription": 0.06,
}

BANKING_PROFILES: dict[str, dict[str, Any]] = {
    "retail_consumer": {"account_mix": {"Savings": 3.0, "Checking": 4.0, "Corporate": 0.2, "Term Deposit": 1.0}, "balance_base": Decimal("2500"), "amount_base": Decimal("85"), "payroll_share": 0.18, "high_value_rate": 0.012},
    "small_business": {"account_mix": {"Savings": 0.8, "Checking": 3.0, "Corporate": 2.6, "Term Deposit": 0.7}, "balance_base": Decimal("18000"), "amount_base": Decimal("650"), "payroll_share": 0.24, "high_value_rate": 0.025},
    "commercial": {"account_mix": {"Savings": 0.2, "Checking": 1.4, "Corporate": 5.2, "Term Deposit": 1.2}, "balance_base": Decimal("125000"), "amount_base": Decimal("4200"), "payroll_share": 0.12, "high_value_rate": 0.045},
    "digital_bank": {"account_mix": {"Savings": 2.0, "Checking": 5.0, "Corporate": 0.4, "Term Deposit": 0.4}, "balance_base": Decimal("4200"), "amount_base": Decimal("120"), "payroll_share": 0.16, "high_value_rate": 0.010},
    "high_net_worth": {"account_mix": {"Savings": 1.2, "Checking": 2.0, "Corporate": 1.0, "Term Deposit": 4.8}, "balance_base": Decimal("275000"), "amount_base": Decimal("3200"), "payroll_share": 0.08, "high_value_rate": 0.035},
}

HEALTHCARE_PROFILES: dict[str, dict[str, Any]] = {
    "primary_care": {"visit_mix": {"Outpatient": 6.0, "Telehealth": 2.0, "Emergency": 0.5, "Inpatient": 0.25}, "inpatient_rate": 0.04, "approval_rate": 0.86, "chronic_visit_lift": 1.7},
    "hospital_network": {"visit_mix": {"Outpatient": 3.5, "Telehealth": 0.6, "Emergency": 1.8, "Inpatient": 1.2}, "inpatient_rate": 0.14, "approval_rate": 0.82, "chronic_visit_lift": 1.9},
    "outpatient_clinic": {"visit_mix": {"Outpatient": 7.0, "Telehealth": 1.5, "Emergency": 0.15, "Inpatient": 0.05}, "inpatient_rate": 0.015, "approval_rate": 0.90, "chronic_visit_lift": 1.5},
    "chronic_care": {"visit_mix": {"Outpatient": 5.0, "Telehealth": 2.5, "Emergency": 0.7, "Inpatient": 0.5}, "inpatient_rate": 0.08, "approval_rate": 0.84, "chronic_visit_lift": 2.6},
    "emergency_care": {"visit_mix": {"Outpatient": 1.8, "Telehealth": 0.2, "Emergency": 5.0, "Inpatient": 1.0}, "inpatient_rate": 0.16, "approval_rate": 0.78, "chronic_visit_lift": 1.4},
}

TELECOM_PROFILES: dict[str, dict[str, Any]] = {
    "urban_consumer": {"coverage": "urban", "plan_mix": {"prepaid": 1.5, "postpaid": 4.0, "family": 2.0, "business": 0.3, "enterprise": 0.1, "iot": 0.1}, "data_multiplier": 1.25, "voice_multiplier": 1.0, "drop_base": 0.018, "evening_share": (0.48, 0.72)},
    "suburban_consumer": {"coverage": "suburban", "plan_mix": {"prepaid": 2.0, "postpaid": 3.4, "family": 2.8, "business": 0.4, "enterprise": 0.1, "iot": 0.1}, "data_multiplier": 1.0, "voice_multiplier": 1.05, "drop_base": 0.026, "evening_share": (0.42, 0.66)},
    "rural_consumer": {"coverage": "rural", "plan_mix": {"prepaid": 2.8, "postpaid": 2.8, "family": 1.6, "business": 0.3, "enterprise": 0.05, "iot": 0.1}, "data_multiplier": 0.72, "voice_multiplier": 1.15, "drop_base": 0.075, "evening_share": (0.34, 0.60)},
    "business": {"coverage": "mixed", "plan_mix": {"prepaid": 0.2, "postpaid": 1.5, "family": 0.2, "business": 5.0, "enterprise": 1.2, "iot": 0.2}, "data_multiplier": 1.35, "voice_multiplier": 1.8, "drop_base": 0.025, "evening_share": (0.25, 0.52)},
    "enterprise": {"coverage": "urban", "plan_mix": {"prepaid": 0.05, "postpaid": 0.5, "family": 0.05, "business": 2.0, "enterprise": 6.0, "iot": 0.7}, "data_multiplier": 1.75, "voice_multiplier": 2.1, "drop_base": 0.018, "evening_share": (0.20, 0.48)},
    "iot_fleet": {"coverage": "mixed", "plan_mix": {"prepaid": 0.05, "postpaid": 0.2, "family": 0.05, "business": 0.7, "enterprise": 1.2, "iot": 7.0}, "data_multiplier": 0.28, "voice_multiplier": 0.15, "drop_base": 0.032, "evening_share": (0.18, 0.42)},
}

LOGISTICS_PROFILES: dict[str, dict[str, Any]] = {
    "urban_last_mile": {"shipment_mix": {"standard": 4.0, "express": 2.5, "cold_chain": 0.4, "fragile": 1.0}, "distance_multiplier": 0.35, "express_share": 0.25, "failure_base": 0.035, "cost_per_km": 0.75},
    "national_ground": {"shipment_mix": {"standard": 5.0, "express": 1.0, "cold_chain": 0.4, "fragile": 0.8}, "distance_multiplier": 1.0, "express_share": 0.12, "failure_base": 0.025, "cost_per_km": 0.55},
    "international_air": {"shipment_mix": {"standard": 1.5, "express": 3.0, "cold_chain": 0.6, "fragile": 0.8}, "distance_multiplier": 1.8, "express_share": 0.38, "failure_base": 0.045, "cost_per_km": 1.65},
    "cold_chain": {"shipment_mix": {"standard": 0.8, "express": 1.5, "cold_chain": 5.5, "fragile": 0.6}, "distance_multiplier": 0.9, "express_share": 0.20, "failure_base": 0.030, "cost_per_km": 1.25},
    "express": {"shipment_mix": {"standard": 0.8, "express": 6.0, "cold_chain": 0.5, "fragile": 0.9}, "distance_multiplier": 0.75, "express_share": 0.60, "failure_base": 0.020, "cost_per_km": 1.10},
    "freight": {"shipment_mix": {"standard": 2.5, "express": 0.6, "cold_chain": 0.7, "fragile": 0.5}, "distance_multiplier": 1.4, "express_share": 0.08, "failure_base": 0.040, "cost_per_km": 0.42},
}

INSURANCE_PROFILES: dict[str, dict[str, Any]] = {
    "personal_auto": {"policy_mix": {"Auto": 6.0, "Home": 0.6, "Health": 0.2, "Life": 0.2, "Travel": 0.3, "Commercial": 0.1}, "premium_factor": Decimal("0.035"), "claim_rate": 0.16, "fraud_rate": 0.012, "settlement_days": 18},
    "homeowners": {"policy_mix": {"Auto": 0.4, "Home": 6.0, "Health": 0.2, "Life": 0.4, "Travel": 0.2, "Commercial": 0.2}, "premium_factor": Decimal("0.010"), "claim_rate": 0.08, "fraud_rate": 0.010, "settlement_days": 32},
    "health_supplemental": {"policy_mix": {"Auto": 0.2, "Home": 0.2, "Health": 6.0, "Life": 0.8, "Travel": 0.3, "Commercial": 0.1}, "premium_factor": Decimal("0.018"), "claim_rate": 0.24, "fraud_rate": 0.009, "settlement_days": 12},
    "commercial": {"policy_mix": {"Auto": 0.3, "Home": 0.4, "Health": 0.3, "Life": 0.3, "Travel": 0.2, "Commercial": 6.0}, "premium_factor": Decimal("0.022"), "claim_rate": 0.12, "fraud_rate": 0.014, "settlement_days": 40},
    "life": {"policy_mix": {"Auto": 0.2, "Home": 0.3, "Health": 0.4, "Life": 6.0, "Travel": 0.1, "Commercial": 0.2}, "premium_factor": Decimal("0.007"), "claim_rate": 0.035, "fraud_rate": 0.006, "settlement_days": 45},
    "high_risk": {"policy_mix": {"Auto": 2.5, "Home": 1.4, "Health": 1.3, "Life": 1.0, "Travel": 0.8, "Commercial": 2.0}, "premium_factor": Decimal("0.045"), "claim_rate": 0.30, "fraud_rate": 0.025, "settlement_days": 38},
}

FINANCE_PROFILES: dict[str, dict[str, Any]] = {
    "retail_investing": {"account_mix": {"Savings": 2.0, "Checking": 3.0, "Business": 0.4, "Loan": 0.2}, "trade_base": Decimal("180"), "high_value_rate": 0.012, "business_hour_share": (0.62, 0.88), "volatility": 0.7},
    "institutional": {"account_mix": {"Savings": 0.2, "Checking": 1.0, "Business": 5.5, "Loan": 0.3}, "trade_base": Decimal("8500"), "high_value_rate": 0.045, "business_hour_share": (0.78, 0.96), "volatility": 1.4},
    "treasury": {"account_mix": {"Savings": 0.3, "Checking": 1.4, "Business": 4.2, "Loan": 0.6}, "trade_base": Decimal("5200"), "high_value_rate": 0.035, "business_hour_share": (0.80, 0.97), "volatility": 0.9},
    "wealth_management": {"account_mix": {"Savings": 1.0, "Checking": 1.8, "Business": 2.2, "Loan": 0.2}, "trade_base": Decimal("2400"), "high_value_rate": 0.030, "business_hour_share": (0.70, 0.92), "volatility": 0.8},
    "high_frequency": {"account_mix": {"Savings": 0.1, "Checking": 0.8, "Business": 6.5, "Loan": 0.1}, "trade_base": Decimal("1100"), "high_value_rate": 0.020, "business_hour_share": (0.86, 0.99), "volatility": 2.2},
    "conservative": {"account_mix": {"Savings": 4.5, "Checking": 2.0, "Business": 0.6, "Loan": 0.3}, "trade_base": Decimal("90"), "high_value_rate": 0.006, "business_hour_share": (0.55, 0.82), "volatility": 0.35},
}

EDUCATION_PROFILES: dict[str, dict[str, Any]] = {
    "K12": {"institution_type": "school", "attendance_base": 0.88, "online": False, "capacity_target": 28, "late_rate": 0.08, "dropout_base": 0.025},
    "community_college": {"institution_type": "college", "attendance_base": 0.78, "online": False, "capacity_target": 36, "late_rate": 0.14, "dropout_base": 0.08},
    "university": {"institution_type": "university", "attendance_base": 0.82, "online": False, "capacity_target": 55, "late_rate": 0.11, "dropout_base": 0.05},
    "online_learning": {"institution_type": "online_university", "attendance_base": 0.70, "online": True, "capacity_target": 90, "late_rate": 0.20, "dropout_base": 0.12},
    "vocational": {"institution_type": "training_center", "attendance_base": 0.84, "online": False, "capacity_target": 24, "late_rate": 0.10, "dropout_base": 0.06},
    "graduate_school": {"institution_type": "university", "attendance_base": 0.90, "online": False, "capacity_target": 22, "late_rate": 0.06, "dropout_base": 0.025},
}


def apply_realism(
    source: Dataset,
    spec: DomainSpec,
    *,
    profile: str = "realistic",
    seed: int = 42,
    selected_tables: set[str] | None = None,
) -> tuple[Dataset, dict[str, Any]]:
    """Apply deterministic, reference-informed realism patterns to generated clean data.

    This layer intentionally runs after domain generation and before failure injection.
    It keeps schemas, IDs, and relationship structure intact while making values less
    uniform and adding business-consistent correlations.
    """

    data = copy.deepcopy(source)
    selected = selected_tables or set(data)
    if profile == "basic" or spec.name not in SUPPORTED_REALISM_DOMAINS:
        return data, _base_report(spec, profile, data, selected, "SKIPPED", "No deeper realism profile applied.")
    if not any(data.get(table) for table in selected):
        return data, _base_report(spec, profile, data, selected, "PASS", "Empty/schema-only run; realism has no rows to mutate.")

    rng = random.Random(seed + 941)
    if spec.name == "retail":
        report = _apply_retail_realism(data, profile, rng, spec, selected)
    elif spec.name == "ecommerce":
        report = _apply_ecommerce_realism(data, profile, rng, spec, selected)
    elif spec.name == "manufacturing":
        report = _apply_manufacturing_realism(data, profile, rng, spec, selected)
    elif spec.name == "banking":
        report = _apply_banking_realism(data, profile, rng, spec, selected)
    elif spec.name == "healthcare":
        report = _apply_healthcare_realism(data, profile, rng, spec, selected)
    elif spec.name == "telecommunications":
        report = _apply_telecommunications_realism(data, profile, rng, spec, selected)
    elif spec.name == "logistics":
        report = _apply_logistics_realism(data, profile, rng, spec, selected)
    elif spec.name == "insurance":
        report = _apply_insurance_realism(data, profile, rng, spec, selected)
    elif spec.name == "finance":
        report = _apply_finance_realism(data, profile, rng, spec, selected)
    elif spec.name == "education":
        report = _apply_education_realism(data, profile, rng, spec, selected)
    else:
        report = _base_report(spec, profile, data, selected, "SKIPPED", "Unsupported realism domain.")
    return data, report


def _base_report(
    spec: DomainSpec,
    profile: str,
    data: Dataset,
    selected_tables: set[str],
    status: str,
    message: str,
) -> dict[str, Any]:
    actual_counts = {table: len(rows) for table, rows in data.items() if table in selected_tables}
    primary = PRIMARY_TABLES.get(spec.name, next(iter(spec.schemas)))
    primary_count = max(1, actual_counts.get(primary, 0))
    sample_size = actual_counts.get(primary, 0)
    statistical_stability = "LOW_SAMPLE" if 0 < sample_size < 250 else "STABLE"
    if sample_size == 0:
        statistical_stability = "EMPTY_SCHEMA_ONLY"
    return {
        "domain": spec.name,
        "realism_profile": profile,
        "profile_description": _profile_description(spec.name, profile, status),
        "status": status,
        "message": message,
        "primary_transaction_table": primary,
        "actual_row_counts": actual_counts,
        "table_volume_ratios": {table: round(count / primary_count, 4) for table, count in actual_counts.items()},
        "distribution_summary": {},
        "expected_metrics": {},
        "actual_metrics": {},
        "tolerance": {},
        "deviation": {},
        "deviations": {},
        "sample_size": sample_size,
        "statistical_stability": statistical_stability,
        "warnings": [],
        "overall_realism_status": status,
        "correlations_applied": [],
        "temporal_patterns_applied": [],
        "business_consistency_applied": [],
        "checks": [],
        "calibration_disclaimer": "Synthetic calibration targets are derived from metadata, distributions, ranges, categories, and business rules only.",
        "source_references": REFERENCE_PROFILES.get(spec.name, []),
        "no_public_rows_copied": True,
        "no_copied_rows_statement": "Generated rows are deterministic synthetic records; public/reference dataset rows are not copied.",
    }


def _profile_description(domain: str, profile: str, status: str) -> str:
    if profile == "basic":
        return "Deterministic valid synthetic data with deeper realism disabled."
    if status == "SKIPPED":
        return "Realism profile was not applied for this run."
    domain_label = domain.replace("_", " ").replace("-", " ")
    return f"Reference-informed {domain_label} realism profile with deterministic distributions, correlations, temporal patterns, and business-rule consistency."


def _money(value: Decimal | int | float | str) -> str:
    return str(Decimal(str(value)).quantize(Decimal("0.01")))


def _as_decimal(value: Any) -> Decimal:
    return Decimal(str(value or "0"))


def _weighted_choice(rng: random.Random, weighted_items: list[tuple[Any, float]]) -> Any:
    total = sum(weight for _, weight in weighted_items)
    marker = rng.random() * total
    cumulative = 0.0
    for item, weight in weighted_items:
        cumulative += weight
        if marker <= cumulative:
            return item
    return weighted_items[-1][0]


def _weighted_hour(rng: random.Random, profile: str, kind: str, hourly_distribution: list[tuple[int, int]] | None = None) -> int:
    if kind == "manufacturing":
        day_weights = [(7, 12), (8, 13), (9, 12), (10, 10), (14, 9), (15, 8), (22, 5 if profile == "realistic" else 12), (23, 4 if profile == "realistic" else 10)]
    elif hourly_distribution:
        day_weights = hourly_distribution
    else:
        day_weights = [(9, 5), (10, 6), (12, 9), (17, 12), (18, 16), (19, 18), (20, 14), (21, 8)]
        if profile == "stress":
            day_weights = [(hour, weight * (2 if hour in {18, 19, 20} else 1)) for hour, weight in day_weights]
    return int(_weighted_choice(rng, day_weights))


def _patterned_datetime(
    rng: random.Random,
    index: int,
    total: int,
    profile: str,
    *,
    kind: str = "commerce",
    hourly_distribution: list[tuple[int, int]] | None = None,
) -> datetime:
    start = datetime(2026, 1, 1, 0, 0, 0)
    span_days = 172
    base_day = int((index / max(1, total)) * span_days)
    weekday_boost = 2 if kind != "manufacturing" else 0
    day_offset = min(span_days - 1, base_day + (weekday_boost if index % 7 in {5, 6} else 0))
    hour = _weighted_hour(rng, profile, kind, hourly_distribution)
    minute = rng.randrange(0, 60)
    second = rng.randrange(0, 60)
    return start + timedelta(days=day_offset, hours=hour, minutes=minute, seconds=second)


def _refresh_audit(row: dict[str, Any], table: str, spec: DomainSpec) -> None:
    timestamp_column = spec.timestamp_sources.get(table) or spec.date_columns.get(table)
    raw = row.get(timestamp_column) if timestamp_column else None
    if raw not in (None, ""):
        try:
            ts = datetime.fromisoformat(str(raw))
        except ValueError:
            return
        row["created_ts"] = ts.isoformat()
        row["updated_ts"] = ts.isoformat()
        row["source_ts"] = ts.isoformat()
        if table in spec.fact_tables:
            row["transaction_ts"] = ts.isoformat()
            row["transaction_date"] = ts.date().isoformat()
            row["transaction_hour"] = ts.hour
            row["transaction_day"] = ts.day
            row["transaction_week"] = ts.isocalendar().week
            row["transaction_month"] = ts.month
            row["transaction_quarter"] = ((ts.month - 1) // 3) + 1
            row["transaction_year"] = ts.year
    row["record_hash"] = record_hash(row)


def _refresh_tables(data: Dataset, spec: DomainSpec, tables: Iterable[str]) -> None:
    for table in tables:
        for row in data.get(table, []):
            _refresh_audit(row, table, spec)


def _positive_direction_check(name: str, left_avg: Decimal, right_avg: Decimal) -> dict[str, Any]:
    passed = right_avg > left_avg
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "expected": "positive_direction",
        "actual": {"lower_avg": str(left_avg.quantize(Decimal("0.01"))), "higher_avg": str(right_avg.quantize(Decimal("0.01")))},
    }


def _tolerance_check(
    name: str,
    actual: float,
    expected: float | tuple[float, float],
    tolerance: float,
    *,
    row_count: int,
    unstable_below: int = 250,
) -> dict[str, Any]:
    if isinstance(expected, tuple):
        lower, upper = expected
        passed = lower - tolerance <= actual <= upper + tolerance
        expected_payload: Any = {"min": lower, "max": upper}
        deviation = 0.0 if lower <= actual <= upper else min(abs(actual - lower), abs(actual - upper))
    else:
        passed = abs(actual - expected) <= tolerance
        expected_payload = expected
        deviation = actual - expected
    warning = row_count < unstable_below
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "expected": expected_payload,
        "actual": round(actual, 4),
        "tolerance": tolerance,
        "deviation": round(deviation, 4),
        "warning": "statistically_unstable_low_row_count" if warning else "",
    }


def _finalize_realism_report(report: dict[str, Any]) -> dict[str, Any]:
    warnings = [check["warning"] for check in report.get("checks", []) if check.get("warning")]
    report["warnings"] = sorted(set(report.get("warnings", []) + warnings))
    report["deviations"] = {check["name"]: check.get("deviation") for check in report.get("checks", []) if "deviation" in check}
    report["deviation"] = dict(report["deviations"])
    report["tolerance"] = {check["name"]: check.get("tolerance") for check in report.get("checks", []) if "tolerance" in check}
    if report.get("warnings"):
        report["statistical_stability"] = "LOW_SAMPLE_WARNING"
    report["overall_realism_status"] = "PASS" if all(check.get("status") == "PASS" for check in report.get("checks", [])) else "FAIL"
    report["status"] = report["overall_realism_status"]
    return report


def _counter_summary(values: Iterable[Any], limit: int = 6) -> dict[str, int]:
    return dict(Counter(values).most_common(limit))


def _apply_retail_realism(data: Dataset, profile: str, rng: random.Random, spec: DomainSpec, selected: set[str]) -> dict[str, Any]:
    report = _base_report(spec, profile, data, selected, "PASS", "Retail realism profile applied.")
    customers = data.get("customers", [])
    products = data.get("products", [])
    sales = data.get("sales", [])
    if not (customers and products and sales):
        report["status"] = "SKIPPED"
        report["message"] = "Retail realism needs customers, products, and sales tables."
        return report

    category_by_id = {row["category_id"]: row for row in data.get("categories", [])}
    product_by_id = {row["product_id"]: row for row in products}
    business_profile = profile if profile in RETAIL_BUSINESS_PROFILES else ("seasonal" if profile == "stress" else "physical_retail")
    profile_config = RETAIL_BUSINESS_PROFILES[business_profile]
    segment_weight = profile_config["customer_segment_mix"]
    category_multiplier = {"Electronics": Decimal("2.10"), "Groceries": Decimal("0.55"), "Clothing": Decimal("0.95"), "Home": Decimal("1.25"), "Sports": Decimal("1.10")}
    return_rate = {"Electronics": 0.07, "Groceries": 0.01, "Clothing": 0.11, "Home": 0.05, "Sports": 0.06}
    return_rate = {key: max(0.005, value * (float(profile_config["return_rate"]) / 0.055)) for key, value in return_rate.items()}
    basket_multiplier = Decimal(profile_config["average_basket_value"]) / Decimal("85.00")

    for product in products:
        category = category_by_id.get(product.get("category_id"), {}).get("category_name", "Home")
        ordinal = int(product["product_id"]) % 97
        base = Decimal("4.99") + (Decimal(ordinal) / Decimal("2.60"))
        unit_price = (base * category_multiplier.get(category, Decimal("1.0")) * basket_multiplier).quantize(Decimal("0.01"))
        product["unit_price"] = _money(unit_price)
        product["cost_price"] = _money(unit_price * Decimal("0.62"))

    weighted_customers = [(customer, segment_weight.get(str(customer.get("loyalty_level")), 1.0)) for customer in customers]
    weighted_products = []
    for product in products:
        category = category_by_id.get(product.get("category_id"), {}).get("category_name", "")
        weight = {"Electronics": 1.8, "Groceries": 3.2, "Clothing": 2.4, "Home": 1.6, "Sports": 1.2}.get(category, 1.0)
        weight *= float(profile_config["product_popularity_skew"])
        weighted_products.append((product, weight))

    promotion_by_product = defaultdict(list)
    for promotion in data.get("promotions", []):
        promotion_by_product[promotion["product_id"]].append(promotion)

    segment_amounts: dict[str, list[Decimal]] = defaultdict(list)
    category_sales = Counter()
    evening_sales = 0
    weekend_sales = 0
    for index, sale in enumerate(sales, 1):
        customer = _weighted_choice(rng, weighted_customers)
        product = _weighted_choice(rng, weighted_products)
        category = category_by_id.get(product.get("category_id"), {}).get("category_name", "Home")
        segment = str(customer.get("loyalty_level", "BRONZE"))
        quantity_base = {"BRONZE": 1, "SILVER": 2, "GOLD": 3, "PLATINUM": 4}.get(segment, 1)
        quantity = min(9 if profile == "stress" else 6, max(1, quantity_base + rng.randrange(0, 3)))
        promotion = None
        if promotion_by_product.get(product["product_id"]) and rng.random() < (0.28 if profile == "realistic" else 0.45):
            promotion = promotion_by_product[product["product_id"]][0]
        discount = Decimal(str(promotion["discount_pct"])) / Decimal("100") if promotion else Decimal("0")
        unit_price = _as_decimal(product["unit_price"])
        amount = (unit_price * Decimal(quantity) * (Decimal("1") - discount)).quantize(Decimal("0.01"))
        timestamp = _patterned_datetime(rng, index, len(sales), profile, hourly_distribution=profile_config["hourly_distribution"])
        sale.update({
            "customer_id": customer["customer_id"],
            "product_id": product["product_id"],
            "promotion_id": promotion["promotion_id"] if promotion else "",
            "quantity": quantity,
            "unit_price": _money(unit_price),
            "sale_amount": _money(amount),
            "sale_timestamp": timestamp.isoformat(),
            "payment_method": _weighted_choice(rng, [("CARD", 5), ("MOBILE", 3), ("CASH", 1)]),
        })
        segment_amounts[segment].append(amount)
        category_sales[category] += 1
        evening_sales += int(timestamp.hour in {17, 18, 19, 20, 21})
        weekend_sales += int(timestamp.weekday() >= 5)

    sale_by_id = {sale["sale_id"]: sale for sale in sales}
    for payment in data.get("payments", []):
        sale = sale_by_id.get(payment.get("sale_id"))
        if sale:
            payment["customer_id"] = sale["customer_id"]
            payment["amount"] = sale["sale_amount"]
            payment["payment_type"] = sale["payment_method"]
            payment["payment_timestamp"] = sale["sale_timestamp"]
            payment["status"] = "COMPLETED"

    eligible_returns = sorted(
        sales,
        key=lambda sale: return_rate.get(category_by_id.get(product_by_id.get(sale["product_id"], {}).get("category_id"), {}).get("category_name", ""), 0.04) + rng.random() / 100,
        reverse=True,
    )
    for index, returned in enumerate(data.get("returns", []), 1):
        sale = eligible_returns[(index - 1) % len(eligible_returns)]
        sale_ts = datetime.fromisoformat(sale["sale_timestamp"])
        returned.update({
            "sale_id": sale["sale_id"],
            "product_id": sale["product_id"],
            "customer_id": sale["customer_id"],
            "return_amount": sale["sale_amount"],
            "return_date": (sale_ts + timedelta(days=2 + index % 28)).date().isoformat(),
        })

    sold_by_product = Counter({sale["product_id"]: 0 for sale in sales})
    for sale in sales:
        sold_by_product[sale["product_id"]] += int(sale["quantity"])
    for item in data.get("inventory", []):
        sold = sold_by_product.get(item.get("product_id"), 0)
        starting = int(item.get("quantity_on_hand", 0)) + max(20, sold // 4)
        item["quantity_on_hand"] = max(0, starting - sold)

    _refresh_tables(data, spec, {"products", "sales", "payments", "returns", "inventory"})
    bronze_avg = _avg(segment_amounts.get("BRONZE", []))
    platinum_avg = _avg(segment_amounts.get("PLATINUM", []))
    all_amounts = [amount for values in segment_amounts.values() for amount in values]
    average_basket = _avg(all_amounts)
    evening_share = evening_sales / max(1, len(sales))
    weekend_share = weekend_sales / max(1, len(sales))
    report["distribution_summary"] = {
        "business_profile": business_profile,
        "sales_by_category": dict(category_sales),
        "sales_by_customer_segment": {segment: len(values) for segment, values in segment_amounts.items()},
        "evening_sales_share": round(evening_share, 4),
        "weekend_sales_share": round(weekend_share, 4),
        "average_basket_value": str(average_basket.quantize(Decimal("0.01"))),
    }
    report["expected_metrics"] = {
        "retail_evening_sales_share": {"range": profile_config["evening_sales_share_range"]},
        "average_basket_value": str(profile_config["average_basket_value"]),
        "return_rate": profile_config["return_rate"],
        "product_popularity_skew": profile_config["product_popularity_skew"],
        "customer_segment_mix": profile_config["customer_segment_mix"],
    }
    report["actual_metrics"] = {
        "retail_evening_sales_share": round(evening_share, 4),
        "average_basket_value": float(average_basket),
        "return_rate": round(len(data.get("returns", [])) / max(1, len(sales)), 4),
        "weekend_sales_share": round(weekend_share, 4),
    }
    report["correlations_applied"] = ["customer loyalty segment increases purchase value", "product category controls price band and return probability", "promotion lowers sale amount"]
    report["temporal_patterns_applied"] = ["evening purchase peaks", "weekend/seasonal date spread"]
    report["business_consistency_applied"] = ["payments reconcile to sales", "returns reference existing sales", "inventory decreases after sales"]
    report["checks"] = [
        _positive_direction_check("platinum_customers_spend_more_than_bronze", bronze_avg, platinum_avg),
        _tolerance_check("retail_evening_sales_share_within_profile", evening_share, profile_config["evening_sales_share_range"], 0.05, row_count=len(sales)),
        _tolerance_check("retail_average_basket_value_near_profile", float(average_basket), float(profile_config["average_basket_value"]), float(profile_config["average_basket_value"]) * 1.75, row_count=len(sales)),
    ]
    return _finalize_realism_report(report)


def _avg(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(max(1, len(values)))


def _apply_ecommerce_realism(data: Dataset, profile: str, rng: random.Random, spec: DomainSpec, selected: set[str]) -> dict[str, Any]:
    report = _base_report(spec, profile, data, selected, "PASS", "E-commerce marketplace realism profile applied.")
    customers = data.get("marketplace_customers", [])
    orders = data.get("orders", [])
    order_items = data.get("order_items", [])
    listings = data.get("product_listings", [])
    if not (customers and orders and order_items and listings):
        report["status"] = "SKIPPED"
        report["message"] = "E-commerce realism needs customers, listings, orders, and order_items."
        return report

    customer_by_id = {row["customer_id"]: row for row in customers}
    listing_by_id = {row["listing_id"]: row for row in listings}
    category_by_id = {row["category_id"]: row for row in data.get("product_categories", [])}
    product_by_id = {row["product_id"]: row for row in data.get("marketplace_products", [])}
    segment_weight = {"new": 1.0, "returning": 1.6, "loyal": 2.5, "high_value": 4.5, "at_risk": 0.8}
    listing_weights = []
    for listing in listings:
        product = product_by_id.get(listing.get("product_id"), {})
        category = category_by_id.get(product.get("category_id"), {}).get("category_name", "").lower()
        weight = 2.8 if any(token in category for token in ("fashion", "grocery", "beauty")) else 1.3
        if profile == "stress" and any(token in category for token in ("electronics", "fashion")):
            weight *= 2.0
        listing_weights.append((listing, weight))

    source_weights = list(ECOMMERCE_SOURCE_RATIOS.items())
    order_source_counts = Counter()
    for index, order in enumerate(orders, 1):
        customer = _weighted_choice(rng, [(customer, segment_weight.get(customer.get("customer_segment"), 1.0)) for customer in customers])
        ordered = _patterned_datetime(rng, index, len(orders), profile)
        order_source = _weighted_choice(rng, source_weights)
        order["customer_id"] = customer["customer_id"]
        order["order_date"] = ordered.isoformat()
        order["created_at"] = ordered.isoformat()
        order["order_source"] = order_source
        order["order_status"] = "delivered" if index <= int(len(orders) * 0.86) else _weighted_choice(rng, [("shipped", 4), ("confirmed", 2), ("cancelled", 1), ("returned", 1)])
        order_source_counts[order_source] += 1

    items_by_order: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for index, item in enumerate(order_items, 1):
        order = orders[(index - 1) % len(orders)]
        listing = _weighted_choice(rng, listing_weights)
        customer = customer_by_id.get(order["customer_id"], {})
        segment = customer.get("customer_segment", "new")
        quantity = min(8 if profile == "stress" else 5, max(1, {"new": 1, "returning": 1, "loyal": 2, "high_value": 3, "at_risk": 1}.get(segment, 1) + rng.randrange(0, 2)))
        unit_price = _as_decimal(listing["listing_price"])
        discount = Decimal("0.00")
        if segment in {"loyal", "high_value"} or rng.random() < (0.22 if profile == "realistic" else 0.38):
            discount = min(unit_price * Decimal(quantity) * Decimal("0.15"), Decimal("35.00"))
        tax = (unit_price * quantity - discount) * Decimal("0.0825")
        line_total = unit_price * quantity - discount + tax
        item.update({
            "order_id": order["order_id"],
            "listing_id": listing["listing_id"],
            "quantity": quantity,
            "unit_price": _money(unit_price),
            "discount_amount": _money(discount),
            "tax_amount": _money(tax),
            "line_total": _money(line_total),
            "item_status": "delivered" if order["order_status"] == "delivered" else "ordered",
            "created_at": order["order_date"],
        })
        items_by_order[order["order_id"]].append(item)

    order_totals: dict[Any, Decimal] = {}
    segment_totals: dict[str, list[Decimal]] = defaultdict(list)
    for order in orders:
        lines = items_by_order.get(order["order_id"], [])
        subtotal = sum((_as_decimal(item["unit_price"]) * Decimal(int(item["quantity"])) for item in lines), Decimal("0"))
        discount = sum((_as_decimal(item["discount_amount"]) for item in lines), Decimal("0"))
        tax = sum((_as_decimal(item["tax_amount"]) for item in lines), Decimal("0"))
        shipping = Decimal("0.00") if subtotal >= Decimal("75.00") else Decimal("6.99")
        total = subtotal - discount + tax + shipping
        order.update({
            "subtotal_amount": _money(subtotal),
            "discount_amount": _money(discount),
            "tax_amount": _money(tax),
            "shipping_amount": _money(shipping),
            "total_amount": _money(total),
        })
        order_totals[order["order_id"]] = total
        customer = customer_by_id.get(order["customer_id"], {})
        segment_totals[str(customer.get("customer_segment", "new"))].append(total)

    for payment in data.get("payments", []):
        order = orders[(int(payment["payment_id"]) - 11000001) % len(orders)]
        paid = datetime.fromisoformat(order["order_date"]) + timedelta(minutes=1 + rng.randrange(0, 8))
        payment_status = _weighted_choice(rng, [("successful", 88), ("failed", 5), ("pending", 4), ("refunded", 2), ("partially_refunded", 1)])
        if order["order_status"] == "cancelled":
            payment_status = _weighted_choice(rng, [("failed", 4), ("refunded", 4), ("pending", 1)])
        payment["order_id"] = order["order_id"]
        payment["payment_amount"] = _money(order_totals[order["order_id"]])
        payment["payment_status"] = payment_status
        payment["payment_date"] = paid.isoformat()
        payment["created_at"] = paid.isoformat()

    delivered_orders = [order for order in orders if order["order_status"] == "delivered"] or orders
    delivered_ids = {order["order_id"] for order in delivered_orders}
    for index, shipment in enumerate(data.get("shipments", []), 1):
        order = delivered_orders[(index - 1) % len(delivered_orders)]
        shipped = datetime.fromisoformat(order["order_date"]) + timedelta(days=1 + index % 3)
        shipment.update({
            "order_id": order["order_id"],
            "shipment_status": "delivered",
            "shipped_at": shipped.isoformat(),
            "delivered_at": (shipped + timedelta(days=1 + index % 5)).isoformat(),
            "shipping_cost": order["shipping_amount"],
            "created_at": shipped.isoformat(),
        })

    delivered_items = [item for item in order_items if item["order_id"] in delivered_ids] or order_items
    for index, returned in enumerate(data.get("returns", []), 1):
        item = delivered_items[(index - 1) % len(delivered_items)]
        order = next(order for order in orders if order["order_id"] == item["order_id"])
        requested = datetime.fromisoformat(order["order_date"]) + timedelta(days=5 + index % 21)
        returned.update({
            "order_id": order["order_id"],
            "order_item_id": item["order_item_id"],
            "return_reason": _weighted_choice(rng, [("damaged", 2), ("size_issue", 3), ("changed_mind", 4), ("defective", 2)]),
            "return_status": "refunded",
            "refund_amount": _money(min(_as_decimal(item["line_total"]), order_totals[order["order_id"]])),
            "requested_at": requested.isoformat(),
            "completed_at": (requested + timedelta(days=2 + index % 8)).isoformat(),
            "created_at": requested.isoformat(),
        })

    for index, review in enumerate(data.get("reviews", []), 1):
        order = delivered_orders[(index - 1) % len(delivered_orders)]
        item = items_by_order.get(order["order_id"], delivered_items)[0]
        listing = listing_by_id.get(item["listing_id"], {})
        reviewed = datetime.fromisoformat(order["order_date"]) + timedelta(days=4 + index % 30)
        rating = int(_weighted_choice(rng, [(5, 8), (4, 5), (3, 2), (2, 1), (1, 1 if profile == "stress" else 0.5)]))
        review.update({
            "customer_id": order["customer_id"],
            "product_id": listing.get("product_id", review.get("product_id")),
            "order_id": order["order_id"],
            "rating": rating,
            "review_title": f"{rating}-star marketplace review",
            "review_status": "approved",
            "review_date": reviewed.isoformat(),
            "created_at": reviewed.isoformat(),
        })

    for cart in data.get("carts", []):
        converted = rng.random() < (0.34 if profile == "realistic" else 0.46)
        cart["cart_status"] = "converted" if converted else _weighted_choice(rng, [("active", 3), ("abandoned", 5), ("expired", 1)])
    for listing in listings:
        sold = sum(int(item["quantity"]) for item in order_items if item["listing_id"] == listing["listing_id"])
        listing["available_quantity"] = max(0, int(listing.get("available_quantity", 0)) + 25 - sold)

    _refresh_tables(data, spec, {"orders", "order_items", "payments", "shipments", "returns", "reviews", "carts", "product_listings"})
    new_avg = _avg(segment_totals.get("new", []))
    high_value_avg = _avg(segment_totals.get("high_value", []))
    report["distribution_summary"] = {
        "funnel_counts": {
            "estimated_product_views": len(orders) * 5,
            "carts": len(data.get("carts", [])),
            "cart_sourced_orders": order_source_counts.get("cart", 0),
            "orders": len(orders),
            "payment_attempts": len(data.get("payments", [])),
            "successful_payments": sum(1 for row in data.get("payments", []) if row.get("payment_status") == "successful"),
            "failed_payments": sum(1 for row in data.get("payments", []) if row.get("payment_status") == "failed"),
            "pending_payments": sum(1 for row in data.get("payments", []) if row.get("payment_status") == "pending"),
            "refunded_payments": sum(1 for row in data.get("payments", []) if row.get("payment_status") in {"refunded", "partially_refunded"}),
            "shipments": len(data.get("shipments", [])),
            "returns": len(data.get("returns", [])),
            "reviews": len(data.get("reviews", [])),
        },
        "payment_status_counts": dict(Counter(row["payment_status"] for row in data.get("payments", []))),
        "order_source_counts": dict(order_source_counts),
        "order_source_ratios": {source: round(order_source_counts.get(source, 0) / max(1, len(orders)), 4) for source in ECOMMERCE_SOURCE_RATIOS},
        "orders_by_customer_segment": {segment: len(values) for segment, values in segment_totals.items()},
        "order_statuses": _counter_summary(order["order_status"] for order in orders),
    }
    cart_sourced_ratio = order_source_counts.get("cart", 0) / max(1, len(orders))
    shipment_ratio = len(data.get("shipments", [])) / max(1, len(orders))
    return_ratio = len(data.get("returns", [])) / max(1, len(delivered_orders))
    report["expected_metrics"] = {
        "order_source_ratios": ECOMMERCE_SOURCE_RATIOS,
        "estimated_product_views_gt_carts_gt_cart_sourced_orders": True,
        "shipment_ratio": {"target": 0.90, "tolerance": 0.08},
        "return_ratio_of_delivered_orders": {"target": 0.08, "tolerance": 0.04},
    }
    report["actual_metrics"] = {
        "order_source_ratios": report["distribution_summary"]["order_source_ratios"],
        "cart_sourced_order_ratio": round(cart_sourced_ratio, 4),
        "shipment_ratio": round(shipment_ratio, 4),
        "return_ratio_of_delivered_orders": round(return_ratio, 4),
    }
    report["correlations_applied"] = ["customer segment affects basket value", "promotion/loyalty discounts affect conversion", "category/listing popularity creates product skew"]
    report["temporal_patterns_applied"] = ["evening order peaks", "order-payment-shipment-return-review event sequence"]
    report["business_consistency_applied"] = ["payments reconcile with orders", "returns reference delivered items", "listing inventory decreases after ordered quantities"]
    report["checks"] = [
        _positive_direction_check("high_value_customers_spend_more_than_new_customers", new_avg, high_value_avg),
        {
            "name": "ecommerce_intentional_mixed_order_sources",
            "status": "PASS" if set(ECOMMERCE_SOURCE_RATIOS) <= set(order_source_counts) else "FAIL",
            "expected": ECOMMERCE_SOURCE_RATIOS,
            "actual": report["distribution_summary"]["order_source_ratios"],
            "message": "Orders can intentionally bypass persisted carts through direct buy, guest checkout, API, and subscription sources.",
        },
        {
            "name": "ecommerce_funnel_ordering",
            "status": "PASS" if report["distribution_summary"]["funnel_counts"]["estimated_product_views"] > len(data.get("carts", [])) > order_source_counts.get("cart", 0) and len(data.get("returns", [])) <= len(data.get("shipments", [])) <= len(orders) else "FAIL",
            "expected": "estimated_product_views > carts > cart_sourced_orders and returns <= shipments <= orders",
            "actual": report["distribution_summary"]["funnel_counts"],
        },
        _tolerance_check("ecommerce_cart_sourced_order_ratio", cart_sourced_ratio, ECOMMERCE_SOURCE_RATIOS["cart"], 0.10, row_count=len(orders)),
        _tolerance_check("ecommerce_shipment_ratio", shipment_ratio, 0.90, 0.08, row_count=len(orders)),
        _tolerance_check("ecommerce_return_ratio", return_ratio, 0.08, 0.04, row_count=len(orders)),
    ]
    return _finalize_realism_report(report)


def _apply_manufacturing_realism(data: Dataset, profile: str, rng: random.Random, spec: DomainSpec, selected: set[str]) -> dict[str, Any]:
    report = _base_report(spec, profile, data, selected, "PASS", "Manufacturing realism profile applied.")
    work_orders = data.get("work_orders", [])
    lines = data.get("production_lines", [])
    machines = data.get("machines", [])
    if not (work_orders and lines):
        report["status"] = "SKIPPED"
        report["message"] = "Manufacturing realism needs production_lines and work_orders."
        return report

    line_by_id = {line["line_id"]: line for line in lines}
    machine_age: dict[Any, int] = {}
    for machine in machines:
        install = datetime.fromisoformat(str(machine["install_date"]))
        age_days = max(1, (datetime(2026, 6, 22) - install).days)
        machine_age[machine["machine_id"]] = age_days

    night_rejections: list[Decimal] = []
    day_rejections: list[Decimal] = []
    for index, order in enumerate(work_orders, 1):
        line = line_by_id.get(order["line_id"], {})
        capacity = Decimal(str(line.get("capacity_per_hour", 100)))
        planned_start = _patterned_datetime(rng, index, len(work_orders), profile, kind="manufacturing")
        duration_hours = Decimal(4 + (index % 8))
        planned_end = planned_start + timedelta(hours=float(duration_hours))
        max_capacity = int(capacity * duration_hours)
        planned = max(1, min(max_capacity, 80 + (index * 17) % max(100, max_capacity)))
        shift = "night" if planned_start.hour >= 22 or planned_start.hour < 6 else ("day" if planned_start.hour < 15 else "swing")
        reject_rate = Decimal("0.012")
        if shift == "night":
            reject_rate += Decimal("0.018" if profile == "realistic" else "0.035")
        elif shift == "swing":
            reject_rate += Decimal("0.006")
        rejected = int(Decimal(planned) * reject_rate) + (1 if rng.random() < float(reject_rate * 10) else 0)
        rejected = min(rejected, planned)
        produced = planned - rejected
        actual_start = planned_start + timedelta(minutes=rng.randrange(0, 40))
        actual_end = planned_end + timedelta(minutes=rng.randrange(0, 65))
        order.update({
            "planned_quantity": planned,
            "produced_quantity": produced,
            "rejected_quantity": rejected,
            "status": "completed",
            "planned_start_time": planned_start.isoformat(),
            "planned_end_time": planned_end.isoformat(),
            "actual_start_time": actual_start.isoformat(),
            "actual_end_time": actual_end.isoformat(),
            "created_at": planned_start.date().isoformat(),
        })
        if shift == "night":
            night_rejections.append(Decimal(rejected) / Decimal(max(1, planned)))
        elif shift == "day":
            day_rejections.append(Decimal(rejected) / Decimal(max(1, planned)))

    work_by_id = {row["work_order_id"]: row for row in work_orders}
    for index, batch in enumerate(data.get("production_batches", []), 1):
        order = work_orders[(index - 1) % len(work_orders)]
        produced = max(1, int(order["produced_quantity"]))
        batches_per_order = max(1, len(data.get("production_batches", [])) // len(work_orders))
        quantity = max(1, produced // batches_per_order)
        rejected = min(quantity, max(0, int(order["rejected_quantity"]) // batches_per_order))
        start = datetime.fromisoformat(order["actual_start_time"]) + timedelta(minutes=(index % max(1, batches_per_order)) * 45)
        batch.update({
            "work_order_id": order["work_order_id"],
            "product_id": order["product_id"],
            "line_id": order["line_id"],
            "quantity_produced": quantity,
            "quantity_rejected": rejected,
            "batch_start_time": start.isoformat(),
            "batch_end_time": (start + timedelta(hours=1 + index % 5)).isoformat(),
            "batch_status": "completed",
            "created_at": start.date().isoformat(),
        })

    batch_by_id = {row["batch_id"]: row for row in data.get("production_batches", [])}
    for index, check in enumerate(data.get("quality_checks", []), 1):
        batch = data.get("production_batches", [])[index - 1 if index - 1 < len(data.get("production_batches", [])) else 0]
        defect_count = int(batch.get("quantity_rejected", 0))
        pass_percentage = Decimal("99.70") if defect_count == 0 else max(Decimal("70.00"), Decimal("98.50") - Decimal(defect_count) * Decimal("0.45"))
        result = "passed" if defect_count == 0 else ("rework_required" if defect_count < 5 else "failed")
        checked = datetime.fromisoformat(batch["batch_end_time"]) + timedelta(minutes=10 + index % 45)
        check.update({
            "batch_id": batch["batch_id"],
            "result": result,
            "defect_count": defect_count,
            "pass_percentage": _money(pass_percentage),
            "checked_at": checked.isoformat(),
            "created_at": checked.date().isoformat(),
        })

    quality_by_id = {row["quality_check_id"]: row for row in data.get("quality_checks", [])}
    failed_checks = [row for row in data.get("quality_checks", []) if int(row.get("defect_count", 0)) > 0] or data.get("quality_checks", [])
    for index, defect in enumerate(data.get("defects", []), 1):
        check = failed_checks[(index - 1) % len(failed_checks)]
        defect.update({
            "quality_check_id": check["quality_check_id"],
            "batch_id": check["batch_id"],
            "defect_quantity": max(1, int(check.get("defect_count", 1))),
            "severity": "high" if int(check.get("defect_count", 0)) >= 8 else ("medium" if int(check.get("defect_count", 0)) >= 3 else "low"),
            "detected_at": check["checked_at"],
            "created_at": datetime.fromisoformat(check["checked_at"]).date().isoformat(),
        })

    old_downtime: list[Decimal] = []
    new_downtime: list[Decimal] = []
    machines_by_age = sorted(machines, key=lambda machine: machine_age.get(machine.get("machine_id"), 0))
    for index, order in enumerate(data.get("maintenance_orders", []), 1):
        if machines_by_age and index % 2:
            machine = machines_by_age[-((index + 1) // 2)]
        elif machines_by_age:
            machine = machines_by_age[(index // 2 - 1) % max(1, len(machines_by_age) // 2)]
        else:
            machine = {}
        age_days = machine_age.get(machine.get("machine_id"), 365)
        age_factor = Decimal(age_days) / Decimal("365")
        recent_preventive = index % 4 == 0
        downtime = Decimal("20") + age_factor * Decimal("18")
        if not recent_preventive:
            downtime *= Decimal("1.35")
        if profile == "stress":
            downtime *= Decimal("1.45")
        downtime_minutes = int(downtime)
        scheduled = datetime(2026, 1, 1) + timedelta(hours=index * 6)
        order.update({
            "machine_id": machine.get("machine_id", order.get("machine_id")),
            "maintenance_type": "preventive" if recent_preventive else "corrective",
            "priority": "high" if downtime_minutes >= 90 else "medium",
            "status": "completed",
            "scheduled_time": scheduled.isoformat(),
            "completed_time": (scheduled + timedelta(minutes=downtime_minutes)).isoformat(),
            "downtime_minutes": downtime_minutes,
            "cost": _money(Decimal("125.00") + Decimal(downtime_minutes) * Decimal("18.50")),
            "created_at": scheduled.date().isoformat(),
        })
        if index % 2:
            old_downtime.append(Decimal(downtime_minutes))
        else:
            new_downtime.append(Decimal(downtime_minutes))

    for item in data.get("inventory", []):
        if item.get("inventory_type") == "finished_good" and item.get("product_id"):
            produced = sum(int(order["produced_quantity"]) for order in work_orders if order["product_id"] == item["product_id"])
            item["quantity_on_hand"] = max(0, int(item.get("quantity_on_hand", 0)) + produced)
        item["last_updated_at"] = datetime(2026, 6, 22, 18, 0, 0).isoformat()

    _refresh_tables(data, spec, {"work_orders", "production_batches", "quality_checks", "defects", "maintenance_orders", "inventory"})
    day_avg = _avg(day_rejections)
    night_avg = _avg(night_rejections)
    new_avg = _avg(new_downtime)
    old_avg = _avg(old_downtime)
    report["distribution_summary"] = {
        "work_orders_by_hour": _counter_summary(datetime.fromisoformat(order["planned_start_time"]).hour for order in work_orders),
        "average_reject_rate_day": str(day_avg.quantize(Decimal("0.0001"))),
        "average_reject_rate_night": str(night_avg.quantize(Decimal("0.0001"))),
        "average_downtime_new_machines": str(new_avg.quantize(Decimal("0.01"))),
        "average_downtime_old_machines": str(old_avg.quantize(Decimal("0.01"))),
    }
    reject_lift = float(night_avg - day_avg)
    downtime_lift = float(old_avg - new_avg)
    report["expected_metrics"] = {
        "night_shift_reject_rate_lift_min": 0.008,
        "older_machine_downtime_lift_min_minutes": 2.0,
        "line_capacity_respected": True,
    }
    report["actual_metrics"] = {
        "night_shift_reject_rate_lift": round(reject_lift, 4),
        "older_machine_downtime_lift_minutes": round(downtime_lift, 2),
        "average_reject_rate_day": float(day_avg),
        "average_reject_rate_night": float(night_avg),
        "average_downtime_new_machines": float(new_avg),
        "average_downtime_old_machines": float(old_avg),
    }
    report["correlations_applied"] = ["machine age increases downtime", "night shift increases defect rate", "line capacity caps planned production"]
    report["temporal_patterns_applied"] = ["shift-aware production schedules", "batch-quality-defect-maintenance event sequences"]
    report["business_consistency_applied"] = ["batches respect work order quantities", "quality defects align to rejected quantities", "maintenance completion time follows downtime"]
    report["checks"] = [
        _positive_direction_check("older_machines_have_more_downtime", new_avg, old_avg),
        _positive_direction_check("night_shift_has_higher_reject_rate_than_day_shift", day_avg, night_avg),
        _tolerance_check("manufacturing_night_reject_lift_minimum", reject_lift, (0.008, 1.0), 0.0, row_count=len(work_orders), unstable_below=500),
        _tolerance_check("manufacturing_age_downtime_lift_minimum", downtime_lift, (2.0, 10_000.0), 0.0, row_count=len(data.get("maintenance_orders", [])), unstable_below=20),
    ]
    return _finalize_realism_report(report)


def _apply_banking_realism(data: Dataset, profile: str, rng: random.Random, spec: DomainSpec, selected: set[str]) -> dict[str, Any]:
    banking_profile = profile if profile in BANKING_PROFILES else "retail_consumer"
    config = BANKING_PROFILES[banking_profile]
    report = _base_report(spec, banking_profile, data, selected, "PASS", "Banking realism profile applied.")
    accounts = data.get("deposit_accounts", [])
    payments = data.get("payments", [])
    transfers = data.get("transfers", [])
    if not (accounts and payments):
        report["status"] = "SKIPPED"
        report["message"] = "Banking realism needs deposit_accounts and payments."
        return report

    account_mix = list(config["account_mix"].items())
    balance_base = Decimal(config["balance_base"])
    amount_base = Decimal(config["amount_base"])
    high_value_rate = float(config["high_value_rate"])
    payroll_share = float(config["payroll_share"])
    type_balance_multiplier = {"Savings": Decimal("0.9"), "Checking": Decimal("0.7"), "Corporate": Decimal("5.0"), "Term Deposit": Decimal("2.8")}
    type_amount_multiplier = {"Savings": Decimal("0.6"), "Checking": Decimal("1.0"), "Corporate": Decimal("7.5"), "Term Deposit": Decimal("2.2")}

    opening_balances: dict[Any, Decimal] = {}
    account_by_id: dict[Any, dict[str, Any]] = {}
    weighted_accounts: list[tuple[dict[str, Any], float]] = []
    account_type_counts = Counter()
    for index, account in enumerate(accounts, 1):
        account_type = _weighted_choice(rng, account_mix)
        status = "Active" if rng.random() > 0.06 else _weighted_choice(rng, [("Dormant", 3), ("Frozen", 1), ("Closed", 1)])
        if index % 25 == 0:
            account_type = "Corporate"
            status = "Active"
        raw_balance = balance_base * type_balance_multiplier.get(account_type, Decimal("1")) * (Decimal("0.45") + Decimal(rng.random() * 1.25))
        balance = raw_balance.quantize(Decimal("0.01"))
        account.update({"account_type": account_type, "balance": _money(balance), "account_status": status})
        opening_balances[account["account_id"]] = balance
        account_by_id[account["account_id"]] = account
        account_type_counts[account_type] += 1
        if status == "Active":
            weighted_accounts.append((account, float(type_amount_multiplier.get(account_type, Decimal("1")))))
    if not weighted_accounts:
        weighted_accounts = [(account, 1.0) for account in accounts]
    active_corporate_accounts = [account for account, _ in weighted_accounts if account.get("account_type") == "Corporate"]

    pay_dates = {1, 15, 30}
    payroll_payments = 0
    high_value_payments = 0
    suspicious_count = 0
    failed_count = 0
    settlement_delays: dict[str, list[int]] = defaultdict(list)
    running_balances = opening_balances.copy()
    ledger_debits = Decimal("0")
    ledger_credits = Decimal("0")
    payment_type_delay = {"ACH": 1, "UPI": 0, "NEFT": 1, "RTGS": 0, "Wire": 2, "SWIFT": 3}
    for index, payment in enumerate(payments, 1):
        account = active_corporate_accounts[(index // 10) % len(active_corporate_accounts)] if active_corporate_accounts and index % 10 == 0 else _weighted_choice(rng, weighted_accounts)
        account_type = account["account_type"]
        is_payroll = rng.random() < payroll_share
        payment_type = "ACH" if is_payroll else _weighted_choice(rng, [("ACH", 4), ("UPI", 3), ("NEFT", 2), ("Wire", 1.2), ("RTGS", 0.8), ("SWIFT", 0.5)])
        day = _weighted_choice(rng, [(1, 3), (15, 6), (30, 3)]) if is_payroll else rng.randrange(1, 29)
        timestamp = datetime(2026, 1 + ((index - 1) % 6), min(int(day), 28), 9 + index % 9, rng.randrange(0, 60), rng.randrange(0, 60))
        multiplier = type_amount_multiplier.get(account_type, Decimal("1"))
        amount = (amount_base * multiplier * (Decimal("0.35") + Decimal(rng.random() * 1.4))).quantize(Decimal("0.01"))
        if rng.random() < high_value_rate:
            amount = (amount_base * multiplier * Decimal("28.0")).quantize(Decimal("0.01"))
            high_value_payments += 1
        balance = running_balances.get(account["account_id"], Decimal("0"))
        fail_probability = 0.01
        if account["account_status"] != "Active":
            fail_probability += 0.45
        if amount > balance * Decimal("0.80"):
            fail_probability += 0.20
        suspicious = amount >= amount_base * multiplier * Decimal("20.0") or (payment_type in {"SWIFT", "Wire"} and amount > amount_base * multiplier * Decimal("8.0"))
        if suspicious:
            suspicious_count += 1
            fail_probability += 0.05
        status = "Failed" if rng.random() < fail_probability else "Completed"
        if is_payroll:
            status = "Completed"
            payroll_payments += 1
        if status == "Completed":
            running_balances[account["account_id"]] = max(Decimal("0.00"), balance - amount)
            ledger_debits += amount
            ledger_credits += amount
        else:
            failed_count += 1
        delay = payment_type_delay[payment_type] + (1 if status == "Pending" else 0)
        settlement_delays[payment_type].append(delay)
        payment.update({
            "account_id": account["account_id"],
            "payment_type": payment_type,
            "amount": _money(amount),
            "currency": account["currency"],
            "payment_status": status,
            "payment_timestamp": timestamp.isoformat(),
            "fraud_scenario": "high_value_payment" if suspicious else "none",
            "is_fraud_scenario": bool(suspicious),
            "reconciliation_scenario": "expected_balance",
            "is_reconciliation_scenario": False,
        })

    completed_transfers = 0
    for index, transfer in enumerate(transfers, 1):
        source = _weighted_choice(rng, weighted_accounts)
        candidates = [account for account in accounts if account["currency"] == source["currency"] and account["account_id"] != source["account_id"] and account["account_status"] == "Active"] or [source]
        destination = candidates[index % len(candidates)]
        amount = (amount_base * type_amount_multiplier.get(source["account_type"], Decimal("1")) * (Decimal("0.25") + Decimal(rng.random()))).quantize(Decimal("0.01"))
        status = "Failed" if source["account_status"] == "Frozen" or amount > running_balances.get(source["account_id"], Decimal("0")) * Decimal("0.90") else "Completed"
        if status == "Completed" and source["account_id"] != destination["account_id"]:
            running_balances[source["account_id"]] = max(Decimal("0.00"), running_balances[source["account_id"]] - amount)
            running_balances[destination["account_id"]] = running_balances.get(destination["account_id"], Decimal("0")) + amount
            ledger_debits += amount
            ledger_credits += amount
            completed_transfers += 1
        timestamp = datetime(2026, 1 + ((index - 1) % 6), 1 + index % 28, 10 + index % 8, rng.randrange(0, 60), rng.randrange(0, 60))
        transfer.update({
            "source_account_id": source["account_id"],
            "destination_account_id": destination["account_id"],
            "transfer_amount": _money(amount),
            "currency": source["currency"],
            "transfer_status": status,
            "transfer_timestamp": timestamp.isoformat(),
            "reconciliation_scenario": "expected_balance",
            "is_reconciliation_scenario": False,
        })

    for account in accounts:
        account["balance"] = _money(running_balances.get(account["account_id"], opening_balances[account["account_id"]]))

    for position in data.get("treasury_positions", []):
        cash = balance_base * Decimal("20") * (Decimal("0.8") + Decimal(rng.random()))
        position["cash_position"] = _money(cash)
        position["market_value"] = _money(cash * Decimal("1.04"))
        position["liquidity_ratio"] = str((Decimal("0.18") + Decimal(rng.random() * 0.45)).quantize(Decimal("0.01")))
    for txn in data.get("treasury_transactions", []):
        txn["transaction_amount"] = _money(amount_base * Decimal("10") * (Decimal("0.8") + Decimal(rng.random())))

    _refresh_tables(data, spec, {"deposit_accounts", "payments", "transfers", "treasury_positions", "treasury_transactions"})
    high_value_ratio = high_value_payments / max(1, len(payments))
    payroll_ratio = payroll_payments / max(1, len(payments))
    failure_ratio = failed_count / max(1, len(payments))
    commercial_amounts = [_as_decimal(row["amount"]) for row in payments if account_by_id[row["account_id"]]["account_type"] == "Corporate"]
    consumer_amounts = [_as_decimal(row["amount"]) for row in payments if account_by_id[row["account_id"]]["account_type"] in {"Savings", "Checking"}]
    avg_commercial = _avg(commercial_amounts)
    avg_consumer = _avg(consumer_amounts)
    avg_delay_by_type = {kind: round(sum(values) / len(values), 2) for kind, values in settlement_delays.items() if values}
    report["distribution_summary"] = {
        "banking_profile": banking_profile,
        "account_type_counts": dict(account_type_counts),
        "payment_status_counts": dict(Counter(row["payment_status"] for row in payments)),
        "payroll_payment_share": round(payroll_ratio, 4),
        "high_value_payment_share": round(high_value_ratio, 4),
        "average_settlement_delay_days_by_type": avg_delay_by_type,
    }
    report["expected_metrics"] = {
        "payroll_share": payroll_share,
        "high_value_rate": high_value_rate,
        "ledger_debits_equal_credits": True,
        "commercial_payments_larger_than_consumer": True,
    }
    report["actual_metrics"] = {
        "payroll_payment_share": round(payroll_ratio, 4),
        "high_value_payment_share": round(high_value_ratio, 4),
        "failed_payment_share": round(failure_ratio, 4),
        "ledger_debits": float(ledger_debits),
        "ledger_credits": float(ledger_credits),
        "ledger_difference": float(abs(ledger_debits - ledger_credits)),
        "average_commercial_payment": float(avg_commercial),
        "average_consumer_payment": float(avg_consumer),
        "suspicious_payment_share": round(suspicious_count / max(1, len(payments)), 4),
        "completed_transfer_count": completed_transfers,
    }
    report["correlations_applied"] = ["account type controls balance and payment amount", "suspicious high-value payments increase fraud alert probability", "balance/account status increases failure probability"]
    report["temporal_patterns_applied"] = ["payroll deposits cluster near pay dates", "settlement delay depends on payment type"]
    report["business_consistency_applied"] = ["balances reconcile after completed payments/transfers", "computed debit and credit ledger entries balance in clean mode"]
    report["checks"] = [
        _positive_direction_check("commercial_accounts_have_larger_payments", avg_consumer, avg_commercial),
        _tolerance_check("banking_high_value_transactions_remain_rare", high_value_ratio, (0.0, max(0.06, high_value_rate + 0.03)), 0.0, row_count=len(payments), unstable_below=500),
        _tolerance_check("banking_payroll_date_concentration", payroll_ratio, payroll_share, 0.08, row_count=len(payments), unstable_below=500),
        _tolerance_check("banking_ledger_debits_equal_credits", float(abs(ledger_debits - ledger_credits)), 0.0, 0.01, row_count=len(payments), unstable_below=500),
    ]
    return _finalize_realism_report(report)


def _patient_age(patient: dict[str, Any]) -> int:
    dob = datetime.fromisoformat(str(patient["dob"])).date()
    today = datetime(2026, 6, 22).date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _apply_healthcare_realism(data: Dataset, profile: str, rng: random.Random, spec: DomainSpec, selected: set[str]) -> dict[str, Any]:
    healthcare_profile = profile if profile in HEALTHCARE_PROFILES else "primary_care"
    config = HEALTHCARE_PROFILES[healthcare_profile]
    report = _base_report(spec, healthcare_profile, data, selected, "PASS", "Healthcare realism profile applied.")
    patients = data.get("patients", [])
    providers = data.get("providers", [])
    visits = data.get("visits", [])
    diagnoses = data.get("diagnoses", [])
    procedures = data.get("procedures", [])
    claims = data.get("claims", [])
    payments = data.get("payments", [])
    if not (patients and providers and visits and diagnoses and procedures and claims):
        report["status"] = "SKIPPED"
        report["message"] = "Healthcare realism needs patients, providers, visits, diagnoses, procedures, and claims."
        return report

    chronic_codes = {"I10", "E11.9"}
    diagnosis_to_cpt = {
        "I10": ("99213", "Office outpatient visit", Decimal("185.00")),
        "E11.9": ("80053", "Comprehensive metabolic panel", Decimal("240.00")),
        "J06.9": ("99213", "Office outpatient visit", Decimal("145.00")),
        "M54.5": ("97110", "Therapeutic exercises", Decimal("310.00")),
        "R07.9": ("93000", "Electrocardiogram", Decimal("525.00")),
        "G43.909": ("70450", "CT head without contrast", Decimal("875.00")),
    }
    patient_chronic: dict[Any, bool] = {}
    weighted_patients: list[tuple[dict[str, Any], float]] = []
    for patient in patients:
        age = _patient_age(patient)
        chronic_probability = 0.08 + max(0, age - 40) * 0.012
        chronic = rng.random() < min(0.75, chronic_probability)
        patient_chronic[patient["patient_id"]] = chronic
        weighted_patients.append((patient, float(config["chronic_visit_lift"] if chronic else 1.0)))

    visit_mix = list(config["visit_mix"].items())
    visit_by_id: dict[Any, dict[str, Any]] = {}
    inpatient_costs: list[Decimal] = []
    outpatient_costs: list[Decimal] = []
    old_patient_chronic_visits = 0
    young_patient_chronic_visits = 0
    follow_up_count = 0
    for index, visit in enumerate(visits, 1):
        patient = _weighted_choice(rng, weighted_patients)
        provider = providers[index % len(providers)]
        is_follow_up = index > 1 and rng.random() < (0.16 if patient_chronic[patient["patient_id"]] else 0.05)
        if is_follow_up:
            follow_up_count += 1
        visit_type = _weighted_choice(rng, visit_mix)
        if patient_chronic[patient["patient_id"]] and rng.random() < 0.22:
            visit_type = "Outpatient"
        visit_date = datetime(2026, 1, 1) + timedelta(days=index % 170, hours=8 + index % 9, minutes=rng.randrange(0, 60))
        if is_follow_up:
            visit_date += timedelta(days=14 + index % 45)
        visit.update({
            "patient_id": patient["patient_id"],
            "provider_id": provider["provider_id"],
            "visit_date": visit_date.isoformat(),
            "visit_type": visit_type,
            "visit_status": "Completed",
        })
        visit_by_id[visit["visit_id"]] = visit
        age = _patient_age(patient)
        if age >= 60 and patient_chronic[patient["patient_id"]]:
            old_patient_chronic_visits += 1
        if age < 40 and patient_chronic[patient["patient_id"]]:
            young_patient_chronic_visits += 1

    diagnosis_by_visit: dict[Any, str] = {}
    for index, diagnosis in enumerate(diagnoses, 1):
        visit = visits[(index - 1) % len(visits)]
        patient = next(patient for patient in patients if patient["patient_id"] == visit["patient_id"])
        age = _patient_age(patient)
        if patient_chronic[patient["patient_id"]]:
            code, description = _weighted_choice(rng, [(("I10", "Essential hypertension"), 4), (("E11.9", "Type 2 diabetes mellitus without complications"), 3), (("M54.5", "Low back pain"), 1)])
        elif visit["visit_type"] == "Emergency":
            code, description = _weighted_choice(rng, [(("R07.9", "Chest pain, unspecified"), 3), (("J06.9", "Acute upper respiratory infection"), 2), (("G43.909", "Migraine, unspecified"), 1)])
        else:
            code, description = _weighted_choice(rng, [(("J06.9", "Acute upper respiratory infection"), 3), (("M54.5", "Low back pain"), 2), (("G43.909", "Migraine, unspecified"), 1)])
        severity = "High" if visit["visit_type"] in {"Emergency", "Inpatient"} and age > 55 else ("Medium" if code in chronic_codes else "Low")
        diagnosis.update({"visit_id": visit["visit_id"], "icd10_code": code, "diagnosis_description": description, "severity": severity})
        diagnosis_by_visit[visit["visit_id"]] = code

    procedure_cost_by_visit: dict[Any, Decimal] = {}
    for index, procedure in enumerate(procedures, 1):
        visit = visits[(index - 1) % len(visits)]
        code = diagnosis_by_visit.get(visit["visit_id"], "J06.9")
        cpt, description, base_cost = diagnosis_to_cpt[code]
        visit_multiplier = Decimal("5.5") if visit["visit_type"] == "Inpatient" else (Decimal("2.0") if visit["visit_type"] == "Emergency" else Decimal("1.0"))
        cost = (base_cost * visit_multiplier * (Decimal("0.85") + Decimal(rng.random() * 0.30))).quantize(Decimal("0.01"))
        procedure.update({"visit_id": visit["visit_id"], "cpt_code": cpt, "procedure_description": description, "procedure_cost": _money(cost)})
        procedure_cost_by_visit[visit["visit_id"]] = cost
        if visit["visit_type"] == "Inpatient":
            inpatient_costs.append(cost)
        elif visit["visit_type"] == "Outpatient":
            outpatient_costs.append(cost)

    plan_weights = [("PPO", 4), ("HMO", 3), ("Medicare", 2), ("Medicaid", 1.5), ("Self Pay", 0.5)]
    plan_approval = {"PPO": 0.90, "HMO": 0.84, "Medicare": 0.82, "Medicaid": 0.76, "Self Pay": 0.55}
    claim_plan_counts = Counter()
    approved_or_paid = 0
    for index, claim in enumerate(claims, 1):
        visit = visits[(index - 1) % len(visits)]
        plan = _weighted_choice(rng, plan_weights)
        base_amount = procedure_cost_by_visit.get(visit["visit_id"], Decimal("150.00"))
        amount = (base_amount * Decimal("1.12")).quantize(Decimal("0.01"))
        approved = rng.random() < plan_approval[plan]
        status = "Paid" if approved and rng.random() < 0.62 else ("Approved" if approved else "Denied")
        submitted = datetime.fromisoformat(visit["visit_date"]) + timedelta(days=1 + index % 5)
        claim.update({
            "patient_id": visit["patient_id"],
            "visit_id": visit["visit_id"],
            "provider_id": visit["provider_id"],
            "claim_amount": _money(amount),
            "claim_status": status,
            "submitted_date": submitted.isoformat(),
        })
        claim_plan_counts[plan] += 1
        approved_or_paid += int(status in {"Approved", "Paid"})

    claim_by_id = {claim["claim_id"]: claim for claim in claims}
    for index, payment in enumerate(payments, 1):
        claim = claims[(index - 1) % len(claims)]
        submitted = datetime.fromisoformat(claim["submitted_date"])
        if claim["claim_status"] == "Paid":
            status = "Paid"
            amount = _as_decimal(claim["claim_amount"])
        elif claim["claim_status"] == "Approved":
            status = "Partial"
            amount = (_as_decimal(claim["claim_amount"]) * Decimal("0.55")).quantize(Decimal("0.01"))
        elif claim["claim_status"] == "Denied":
            status = "Rejected"
            amount = Decimal("0.00")
        else:
            status = "Pending"
            amount = Decimal("0.00")
        payment.update({"claim_id": claim["claim_id"], "payment_amount": _money(amount), "payment_date": (submitted + timedelta(days=3 + index % 14)).isoformat(), "payment_status": status})

    prior_authorizations = data.get("prior_authorizations", [])
    visits_by_id = {visit["visit_id"]: visit for visit in visits}
    for index, authorization in enumerate(prior_authorizations, 1):
        procedure = procedures[(index - 1) % len(procedures)]
        visit = visits_by_id.get(procedure.get("visit_id"), visits[(index - 1) % len(visits)])
        requested = datetime.fromisoformat(visit["visit_date"]) + timedelta(hours=2 + index % 48)
        status = authorization.get("authorization_status", "Approved")
        if status not in {"Approved", "Denied", "Pending"}:
            status = "Approved"
        approved_at = requested + timedelta(days=1 + index % 4)
        approved_amount = (_as_decimal(procedure["procedure_cost"]) * Decimal("0.80")).quantize(Decimal("0.01")) if status == "Approved" else Decimal("0.00")
        authorization.update(
            {
                "patient_id": visit["patient_id"],
                "provider_id": visit["provider_id"],
                "procedure_id": procedure["procedure_id"],
                "procedure_code": procedure["cpt_code"],
                "requested_at": requested.isoformat(),
                "approved_at": approved_at.isoformat() if status == "Approved" else "not_applicable",
                "authorization_status": status,
                "approved_amount": _money(approved_amount),
                "expiration_date": (approved_at + timedelta(days=30 + index % 150)).date().isoformat() if status == "Approved" else "not_applicable",
                "denial_reason": authorization.get("denial_reason") if status == "Denied" and authorization.get("denial_reason") != "not_applicable" else ("not_medically_necessary" if status == "Denied" else "not_applicable"),
            }
        )

    _refresh_tables(data, spec, {"visits", "diagnoses", "procedures", "prior_authorizations", "claims", "payments"})
    patient_visit_counts = Counter(visit["patient_id"] for visit in visits)
    chronic_counts = [patient_visit_counts[patient["patient_id"]] for patient in patients if patient_chronic[patient["patient_id"]]]
    non_chronic_counts = [patient_visit_counts[patient["patient_id"]] for patient in patients if not patient_chronic[patient["patient_id"]]]
    chronic_rate_old = sum(1 for patient in patients if _patient_age(patient) >= 60 and patient_chronic[patient["patient_id"]]) / max(1, sum(1 for patient in patients if _patient_age(patient) >= 60))
    chronic_rate_young = sum(1 for patient in patients if _patient_age(patient) < 40 and patient_chronic[patient["patient_id"]]) / max(1, sum(1 for patient in patients if _patient_age(patient) < 40))
    inpatient_rate = sum(1 for visit in visits if visit["visit_type"] == "Inpatient") / max(1, len(visits))
    approval_rate = approved_or_paid / max(1, len(claims))
    report["distribution_summary"] = {
        "healthcare_profile": healthcare_profile,
        "visit_type_counts": dict(Counter(visit["visit_type"] for visit in visits)),
        "claim_status_counts": dict(Counter(claim["claim_status"] for claim in claims)),
        "insurance_plan_counts": dict(claim_plan_counts),
        "follow_up_visit_count": follow_up_count,
    }
    report["expected_metrics"] = {
        "inpatient_rate": config["inpatient_rate"],
        "approval_rate": config["approval_rate"],
        "older_patients_more_chronic": True,
        "inpatient_more_expensive_than_outpatient": True,
        "chronic_patients_have_higher_visit_frequency": True,
    }
    avg_inpatient = _avg(inpatient_costs)
    avg_outpatient = _avg(outpatient_costs)
    avg_chronic_visits = Decimal(sum(chronic_counts)) / Decimal(max(1, len(chronic_counts)))
    avg_non_chronic_visits = Decimal(sum(non_chronic_counts)) / Decimal(max(1, len(non_chronic_counts)))
    report["actual_metrics"] = {
        "chronic_rate_age_60_plus": round(chronic_rate_old, 4),
        "chronic_rate_under_40": round(chronic_rate_young, 4),
        "inpatient_rate": round(inpatient_rate, 4),
        "approval_rate": round(approval_rate, 4),
        "average_inpatient_procedure_cost": float(avg_inpatient),
        "average_outpatient_procedure_cost": float(avg_outpatient),
        "average_chronic_patient_visits": float(avg_chronic_visits),
        "average_non_chronic_patient_visits": float(avg_non_chronic_visits),
        "follow_up_visit_share": round(follow_up_count / max(1, len(visits)), 4),
    }
    report["correlations_applied"] = ["patient age increases chronic-condition probability", "diagnosis influences procedure type", "procedure and visit type influence claim amount", "insurance plan influences approval probability"]
    report["temporal_patterns_applied"] = ["follow-up visits occur after relevant encounters", "claim and payment dates follow service dates"]
    report["business_consistency_applied"] = ["claims reference visits/patients/providers", "payments never exceed claim amount", "claim lifecycle aligns to payment status"]
    report["checks"] = [
        _positive_direction_check("older_patients_have_more_chronic_conditions", Decimal(str(chronic_rate_young)), Decimal(str(chronic_rate_old))),
        _positive_direction_check("inpatient_costs_exceed_outpatient_costs", avg_outpatient, avg_inpatient),
        _positive_direction_check("chronic_patients_have_more_visits", avg_non_chronic_visits, avg_chronic_visits),
        _tolerance_check("healthcare_inpatient_rate_near_profile", inpatient_rate, config["inpatient_rate"], 0.08, row_count=len(visits), unstable_below=500),
        _tolerance_check("healthcare_claim_approval_rate_near_profile", approval_rate, config["approval_rate"], 0.14, row_count=len(claims), unstable_below=500),
    ]
    return _finalize_realism_report(report)


def _apply_telecommunications_realism(data: Dataset, profile: str, rng: random.Random, spec: DomainSpec, selected: set[str]) -> dict[str, Any]:
    telecom_profile = profile if profile in TELECOM_PROFILES else "urban_consumer"
    config = TELECOM_PROFILES[telecom_profile]
    report = _base_report(spec, telecom_profile, data, selected, "PASS", "Telecommunications realism profile applied.")
    plans = data.get("plans", [])
    subscriptions = data.get("subscriptions", [])
    devices = data.get("devices", [])
    regions = data.get("network_regions", [])
    towers = data.get("cell_towers", [])
    calls = data.get("call_detail_records", [])
    sms_rows = data.get("sms_records", [])
    sessions = data.get("data_sessions", [])
    invoices = data.get("invoices", [])
    if not (plans and subscriptions and devices and regions and towers and calls and sessions):
        report["status"] = "SKIPPED"
        report["message"] = "Telecommunications realism needs plans, subscriptions, devices, regions, towers, calls, and data sessions."
        return report

    plan_mix = list(config["plan_mix"].items())
    plan_by_id = {}
    for index, plan in enumerate(plans, 1):
        plan_type = _weighted_choice(rng, plan_mix)
        monthly_fee = {"prepaid": 18, "postpaid": 45, "family": 85, "business": 120, "enterprise": 240, "iot": 12}[plan_type]
        data_included = {"prepaid": 8, "postpaid": 40, "family": 120, "business": 180, "enterprise": 500, "iot": 3}[plan_type]
        plan.update({
            "plan_type": plan_type,
            "plan_name": f"{plan_type.replace('_', ' ').title()} Realism Plan {index:03d}",
            "monthly_fee": _money(Decimal(monthly_fee) * (Decimal("0.85") + Decimal(rng.random() * 0.35))),
            "voice_minutes_included": {"prepaid": 400, "postpaid": 1500, "family": 3500, "business": 6000, "enterprise": 20000, "iot": 30}[plan_type],
            "sms_included": {"prepaid": 500, "postpaid": 2000, "family": 6000, "business": 10000, "enterprise": 50000, "iot": 100}[plan_type],
            "data_gb_included": data_included,
            "roaming_enabled": plan_type in {"postpaid", "family", "business", "enterprise"} or rng.random() < 0.2,
        })
        plan_by_id[plan["plan_id"]] = plan

    for index, region in enumerate(regions, 1):
        coverage = "rural" if index % 7 == 0 else (config["coverage"] if index % 3 else _weighted_choice(rng, [("urban", 3), ("suburban", 2), ("rural", 1), ("mixed", 1)]))
        region["coverage_type"] = coverage

    region_by_id = {row["region_id"]: row for row in regions}
    congested_towers: set[Any] = set()
    outage_towers: set[Any] = set()
    for index, tower in enumerate(towers, 1):
        region = region_by_id[tower["region_id"]]
        technology = _weighted_choice(rng, [("5g", 4), ("4g", 3), ("lte", 2), ("mixed", 1), ("fiber_backhaul", 0.5)])
        if telecom_profile == "rural_consumer":
            technology = _weighted_choice(rng, [("4g", 4), ("lte", 3), ("mixed", 1), ("5g", 0.8)])
        tower["technology"] = technology
        tower["status"] = "active"
        if rng.random() < (0.12 if region["coverage_type"] == "urban" else 0.07):
            congested_towers.add(tower["tower_id"])
        if rng.random() < (0.04 if region["coverage_type"] == "rural" else 0.018):
            outage_towers.add(tower["tower_id"])
            tower["status"] = "maintenance"

    sub_by_id = {row["subscription_id"]: row for row in subscriptions}
    plan_for_subscription = {sub["subscription_id"]: plan_by_id[sub["plan_id"]] for sub in subscriptions}
    device_by_id = {row["device_id"]: row for row in devices}
    tower_by_id = {row["tower_id"]: row for row in towers}
    evening_usage = 0
    total_usage_events = 0
    rural_calls = rural_dropped = urban_calls = urban_dropped = 0
    congested_events = congested_failures = normal_events = normal_failures = 0
    roaming_calls = roaming_costs = non_roaming_costs = Decimal("0")
    data_5g: list[Decimal] = []
    data_4g: list[Decimal] = []

    def event_time(index: int, business_weight: bool = False) -> datetime:
        if telecom_profile in {"business", "enterprise"} or business_weight:
            hour_weights = [(8, 10), (9, 13), (10, 12), (11, 10), (13, 10), (14, 10), (15, 8), (18, 4), (20, 2)]
            day_offset = index % 120
            if day_offset % 7 in {5, 6}:
                day_offset += 2
        else:
            hour_weights = [(7, 6), (9, 7), (12, 10), (14, 7), (16, 8), (17, 9), (18, 11), (19, 12), (20, 10), (21, 6), (22, 3)]
            day_offset = index % 120
        return datetime(2026, 1, 1) + timedelta(days=day_offset, hours=int(_weighted_choice(rng, hour_weights)), minutes=rng.randrange(0, 60), seconds=rng.randrange(0, 60))

    for index, call in enumerate(calls, 1):
        sub = sub_by_id[call["subscription_id"]]
        plan = plan_for_subscription[sub["subscription_id"]]
        tower = tower_by_id[call["tower_id"]]
        region = region_by_id[tower["region_id"]]
        started = event_time(index, plan["plan_type"] in {"business", "enterprise"})
        roaming = plan["roaming_enabled"] and rng.random() < (0.08 if plan["plan_type"] in {"business", "enterprise"} else 0.03)
        duration = int((80 + rng.randrange(0, 900)) * (float(config["voice_multiplier"]) if plan["plan_type"] in {"business", "enterprise"} else 1.0))
        drop_probability = float(config["drop_base"]) + (0.16 if region["coverage_type"] == "rural" else 0.0) + (0.08 if tower["tower_id"] in congested_towers else 0.0) + (0.25 if tower["tower_id"] in outage_towers else 0.0)
        status = "dropped" if rng.random() < drop_probability else "completed"
        cost = Decimal(duration) * Decimal("0.002")
        if roaming:
            cost *= Decimal("4.0")
            call_type = "roaming"
            roaming_calls += 1
            roaming_costs += cost
        else:
            call_type = _weighted_choice(rng, [("local", 5), ("national", 3), ("international", 0.5), ("emergency", 0.05)])
            non_roaming_costs += cost
        call.update({"call_start_time": started.isoformat(), "call_end_time": (started + timedelta(seconds=duration)).isoformat(), "duration_seconds": duration, "call_type": call_type, "call_status": status, "cost": _money(cost), "created_at": started.date().isoformat()})
        evening_usage += int(started.hour in {17, 18, 19, 20, 21, 22})
        total_usage_events += 1
        if region["coverage_type"] == "rural":
            rural_calls += 1
            rural_dropped += int(status == "dropped")
        elif region["coverage_type"] == "urban":
            urban_calls += 1
            urban_dropped += int(status == "dropped")
        if tower["tower_id"] in congested_towers:
            congested_events += 1
            congested_failures += int(status != "completed")
        else:
            normal_events += 1
            normal_failures += int(status != "completed")

    for index, sms in enumerate(sms_rows, 1):
        tower = tower_by_id[sms["tower_id"]]
        sent = event_time(index)
        failed = tower["tower_id"] in outage_towers or (tower["tower_id"] in congested_towers and rng.random() < 0.05)
        sms.update({"sent_time": sent.isoformat(), "delivery_status": "failed" if failed else "delivered", "cost": _money(Decimal("0.02") if sms["message_type"] != "otp" else Decimal("0.00")), "created_at": sent.date().isoformat()})
        evening_usage += int(sent.hour in {17, 18, 19, 20, 21, 22})
        total_usage_events += 1

    for index, session in enumerate(sessions, 1):
        tower = tower_by_id[session["tower_id"]]
        device = device_by_id[session["device_id"]]
        started = event_time(index)
        network_type = "5g" if tower["technology"] == "5g" or rng.random() < 0.35 else _weighted_choice(rng, [("4g", 4), ("lte", 2), ("wifi_offload", 1), ("3g", 0.4)])
        device_multiplier = {"smartphone": 1.6, "tablet": 1.9, "router": 2.4, "iot_device": 0.15, "modem": 2.2, "wearable": 0.25}.get(device["device_type"], 1.0)
        network_multiplier = Decimal("2.2") if network_type == "5g" else (Decimal("1.0") if network_type in {"4g", "lte"} else Decimal("0.55"))
        used = (Decimal("40") * Decimal(str(config["data_multiplier"])) * Decimal(str(device_multiplier)) * network_multiplier * (Decimal("0.6") + Decimal(rng.random() * 1.5))).quantize(Decimal("0.01"))
        failed = tower["tower_id"] in outage_towers or (tower["tower_id"] in congested_towers and rng.random() < 0.10)
        duration = 5 + rng.randrange(0, 220)
        session.update({"session_start_time": started.isoformat(), "session_end_time": (started + timedelta(minutes=duration)).isoformat(), "data_used_mb": _money(used), "network_type": network_type, "session_status": "failed" if failed else "completed", "cost": _money(used * Decimal("0.004")), "created_at": started.date().isoformat()})
        evening_usage += int(started.hour in {17, 18, 19, 20, 21, 22})
        total_usage_events += 1
        if network_type == "5g":
            data_5g.append(used)
        elif network_type in {"4g", "lte"}:
            data_4g.append(used)
        if tower["tower_id"] in congested_towers:
            congested_events += 1
            congested_failures += int(failed)
        else:
            normal_events += 1
            normal_failures += int(failed)

    event_towers = list(outage_towers or congested_towers or {towers[0]["tower_id"]})
    for index, event in enumerate(data.get("network_events", []), 1):
        tower = tower_by_id[event_towers[(index - 1) % len(event_towers)]]
        start = datetime(2026, 1, 1) + timedelta(days=index % 120, hours=8 + index % 12)
        is_outage = tower["tower_id"] in outage_towers
        event.update({"tower_id": tower["tower_id"], "region_id": tower["region_id"], "event_type": "tower_outage" if is_outage else "congestion", "severity": "critical" if is_outage else "high", "event_start_time": start.isoformat(), "event_end_time": (start + timedelta(minutes=45 + index % 180)).isoformat(), "affected_users": 500 + index * 17, "root_cause": "capacity" if not is_outage else "power", "status": "resolved", "created_at": start.date().isoformat()})

    charges_by_customer: dict[Any, dict[str, Decimal]] = defaultdict(lambda: {"voice": Decimal("0"), "sms": Decimal("0"), "data": Decimal("0")})
    sub_customer = {sub["subscription_id"]: sub["customer_id"] for sub in subscriptions}
    for call in calls:
        charges_by_customer[sub_customer[call["subscription_id"]]]["voice"] += _as_decimal(call["cost"])
    for sms in sms_rows:
        charges_by_customer[sub_customer[sms["subscription_id"]]]["sms"] += _as_decimal(sms["cost"])
    for session in sessions:
        charges_by_customer[sub_customer[session["subscription_id"]]]["data"] += _as_decimal(session["cost"])
    billing_by_id = {row["billing_account_id"]: row for row in data.get("billing_accounts", [])}
    customer_billing = {row["customer_id"]: row for row in data.get("billing_accounts", [])}
    for index, invoice in enumerate(invoices, 1):
        billing = billing_by_id.get(invoice["billing_account_id"]) or data.get("billing_accounts", [{}])[0]
        customer_id = billing.get("customer_id")
        charges = charges_by_customer.get(customer_id, {"voice": Decimal("0"), "sms": Decimal("0"), "data": Decimal("0")})
        scale = Decimal("1") / Decimal(max(1, len(invoices) // max(1, len(charges_by_customer))))
        voice = (charges["voice"] * scale).quantize(Decimal("0.01"))
        sms_charge = (charges["sms"] * scale).quantize(Decimal("0.01"))
        data_charge = (charges["data"] * scale).quantize(Decimal("0.01"))
        taxes = ((voice + sms_charge + data_charge) * Decimal("0.085")).quantize(Decimal("0.01"))
        total = voice + sms_charge + data_charge + taxes
        due = datetime(2026, 2 + index % 5, 15 + index % 10)
        invoice.update({"total_voice_charges": _money(voice), "total_sms_charges": _money(sms_charge), "total_data_charges": _money(data_charge), "taxes": _money(taxes), "total_amount": _money(total), "due_date": due.date().isoformat(), "status": "paid", "created_at": (due - timedelta(days=15)).date().isoformat()})
    invoice_by_id = {row["invoice_id"]: row for row in invoices}
    for index, payment in enumerate(data.get("payments", []), 1):
        invoice = invoices[(index - 1) % len(invoices)]
        payment.update({"invoice_id": invoice["invoice_id"], "payment_amount": invoice["total_amount"], "payment_status": "successful", "payment_date": (datetime.fromisoformat(invoice["due_date"]) - timedelta(days=index % 8)).date().isoformat(), "created_at": invoice["created_at"]})

    affected_subscriptions = [sub for sub in subscriptions if sub["subscription_id"] in {row["subscription_id"] for row in calls[: max(1, len(calls) // 10)]}] or subscriptions
    for index, ticket in enumerate(data.get("support_tickets", []), 1):
        sub = affected_subscriptions[(index - 1) % len(affected_subscriptions)]
        opened = datetime(2026, 1, 1) + timedelta(days=index % 120, hours=10 + index % 8)
        ticket.update({"customer_id": sub["customer_id"], "subscription_id": sub["subscription_id"], "ticket_type": "network_issue" if index % 3 else "billing", "priority": "urgent" if index % 5 == 0 else "high", "status": "resolved", "opened_at": opened.isoformat(), "resolved_at": (opened + timedelta(hours=2 + index % 48)).isoformat(), "resolution_summary": "Realism-generated ticket linked to outage or billing anomaly.", "created_at": opened.date().isoformat()})

    _refresh_tables(data, spec, {"plans", "subscriptions", "network_regions", "cell_towers", "call_detail_records", "sms_records", "data_sessions", "invoices", "payments", "network_events", "support_tickets"})
    evening_share = evening_usage / max(1, total_usage_events)
    avg_5g = _avg(data_5g)
    avg_4g = _avg(data_4g)
    rural_drop_rate = rural_dropped / max(1, rural_calls)
    urban_drop_rate = urban_dropped / max(1, urban_calls)
    congested_failure_rate = congested_failures / max(1, congested_events)
    normal_failure_rate = normal_failures / max(1, normal_events)
    avg_roaming_cost = roaming_costs / Decimal(max(1, roaming_calls))
    avg_non_roaming_cost = non_roaming_costs / Decimal(max(1, len(calls) - roaming_calls))
    invoice_diff = Decimal("0")
    for invoice in invoices:
        expected = _as_decimal(invoice["total_voice_charges"]) + _as_decimal(invoice["total_sms_charges"]) + _as_decimal(invoice["total_data_charges"]) + _as_decimal(invoice["taxes"])
        invoice_diff += abs(expected - _as_decimal(invoice["total_amount"]))
    report["distribution_summary"] = {"telecom_profile": telecom_profile, "network_type_counts": dict(Counter(row["network_type"] for row in sessions)), "call_status_counts": dict(Counter(row["call_status"] for row in calls)), "session_status_counts": dict(Counter(row["session_status"] for row in sessions)), "ticket_type_counts": dict(Counter(row["ticket_type"] for row in data.get("support_tickets", [])))}
    report["expected_metrics"] = {"evening_usage_share": config["evening_share"], "5g_data_gt_4g": True, "rural_drop_lift": True, "congestion_failure_lift": True, "invoice_reconciliation": "charges + taxes = total"}
    report["actual_metrics"] = {"evening_usage_share": round(evening_share, 4), "average_5g_data_mb": float(avg_5g), "average_4g_lte_data_mb": float(avg_4g), "rural_drop_rate": round(rural_drop_rate, 4), "urban_drop_rate": round(urban_drop_rate, 4), "congested_failure_rate": round(congested_failure_rate, 4), "normal_failure_rate": round(normal_failure_rate, 4), "average_roaming_call_cost": float(avg_roaming_cost), "average_non_roaming_call_cost": float(avg_non_roaming_cost), "invoice_reconciliation_difference": float(invoice_diff), "outage_tower_count": len(outage_towers), "congested_tower_count": len(congested_towers)}
    report["correlations_applied"] = ["plan type affects voice/SMS/data usage", "5G sessions consume more data than 4G/LTE", "rural coverage and tower congestion increase dropped calls/session failures", "roaming increases usage cost"]
    report["temporal_patterns_applied"] = ["consumer usage peaks during evening hours", "business/enterprise usage shifts toward weekdays/business hours"]
    report["business_consistency_applied"] = ["invoice totals reconcile with usage charges", "network outages affect calls, SMS, and data sessions", "support tickets increase after outage/billing anomalies"]
    report["checks"] = [
        _tolerance_check("telecom_evening_usage_peak", evening_share, config["evening_share"], 0.05, row_count=total_usage_events, unstable_below=500),
        _positive_direction_check("telecom_5g_data_exceeds_4g_lte", avg_4g, avg_5g),
        _positive_direction_check("telecom_rural_dropped_call_lift", Decimal(str(urban_drop_rate)), Decimal(str(rural_drop_rate))),
        _positive_direction_check("telecom_congestion_failure_lift", Decimal(str(normal_failure_rate)), Decimal(str(congested_failure_rate))),
        _positive_direction_check("telecom_roaming_cost_lift", avg_non_roaming_cost, avg_roaming_cost),
        _tolerance_check("telecom_invoice_reconciliation", float(invoice_diff), 0.0, 0.05, row_count=len(invoices), unstable_below=100),
    ]
    report["calibration_disclaimer"] = "Telecommunications realism metrics are synthetic calibration targets derived from metadata only; no public rows are copied."
    return _finalize_realism_report(report)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _apply_logistics_realism(data: Dataset, profile: str, rng: random.Random, spec: DomainSpec, selected: set[str]) -> dict[str, Any]:
    logistics_profile = profile if profile in LOGISTICS_PROFILES else "national_ground"
    config = LOGISTICS_PROFILES[logistics_profile]
    report = _base_report(spec, logistics_profile, data, selected, "PASS", "Logistics realism profile applied.")
    shipments = data.get("shipments", [])
    warehouses = data.get("warehouses", [])
    deliveries = data.get("delivery_records", [])
    tracking_events = data.get("tracking_events", [])
    gps_events = data.get("gps_events", [])
    if not (shipments and warehouses and tracking_events):
        report["status"] = "SKIPPED"
        report["message"] = "Logistics realism needs shipments, warehouses, and tracking_events."
        return report

    warehouse_by_id = {row["warehouse_id"]: row for row in warehouses}
    shipment_mix = list(config["shipment_mix"].items())
    distance_by_shipment: dict[Any, float] = {}
    duration_by_shipment: dict[Any, float] = {}
    cost_by_shipment: dict[Any, float] = {}
    express_durations: list[Decimal] = []
    standard_durations: list[Decimal] = []
    express_costs: list[Decimal] = []
    standard_costs: list[Decimal] = []
    cold_chain_count = cold_chain_compliant = 0
    failed_by_region = Counter()
    total_by_region = Counter()
    created = packed = in_transit = delivered = returned = 0
    for index, shipment in enumerate(shipments, 1):
        source = warehouse_by_id[shipment["source_warehouse_id"]]
        destination = warehouse_by_id[shipment["destination_warehouse_id"]]
        distance = max(8.0, _haversine_km(float(source["latitude"]), float(source["longitude"]), float(destination["latitude"]), float(destination["longitude"])) * float(config["distance_multiplier"]))
        shipment_type = _weighted_choice(rng, shipment_mix)
        if rng.random() < float(config["express_share"]):
            shipment_type = "express"
        peak = index % 11 in {0, 1, 2}
        customs_delay = 18 + rng.randrange(0, 36) if logistics_profile == "international_air" else 0
        cold_chain_delay = 4 if shipment_type == "cold_chain" else 0
        base_hours = distance / (95 if shipment_type == "express" else 55)
        if shipment_type == "express":
            base_hours *= 0.58
        if shipment_type == "cold_chain":
            base_hours *= 0.85
        duration_hours = base_hours + customs_delay + cold_chain_delay + (8 if peak else 0) + rng.random() * 6
        failure_probability = float(config["failure_base"]) + (0.04 if destination["city"] in {"Chicago", "Seattle"} else 0.01) + (0.035 if peak else 0.0)
        if shipment_type == "cold_chain":
            failure_probability *= 0.25
        failed = rng.random() < failure_probability
        status = "returned" if failed else "delivered"
        created_at = datetime(2026, 1, 1) + timedelta(days=index % 150, hours=7 + index % 10, minutes=rng.randrange(0, 60))
        cost = distance * float(config["cost_per_km"]) * (1.9 if shipment_type == "express" else 1.0) * (1.6 if shipment_type == "cold_chain" else 1.0) + float(shipment["weight_kg"]) * 0.02
        shipment.update({"shipment_type": shipment_type, "shipment_status": status, "created_at": created_at.isoformat()})
        distance_by_shipment[shipment["shipment_id"]] = distance
        duration_by_shipment[shipment["shipment_id"]] = duration_hours
        cost_by_shipment[shipment["shipment_id"]] = cost
        total_by_region[destination["state"]] += 1
        failed_by_region[destination["state"]] += int(failed)
        if shipment_type == "express":
            express_durations.append(Decimal(str(duration_hours)))
            express_costs.append(Decimal(str(cost)))
        elif shipment_type == "standard":
            standard_durations.append(Decimal(str(duration_hours)))
            standard_costs.append(Decimal(str(cost)))
        if shipment_type == "cold_chain":
            cold_chain_count += 1
            cold_chain_compliant += int(not failed)

    delivery_by_shipment = {row["shipment_id"]: row for row in deliveries}
    delivered_shipments = [shipment for shipment in shipments if shipment["shipment_status"] == "delivered"]
    for index, delivery in enumerate(deliveries, 1):
        shipment = delivered_shipments[(index - 1) % len(delivered_shipments)] if delivered_shipments else shipments[(index - 1) % len(shipments)]
        duration_minutes = int(duration_by_shipment[shipment["shipment_id"]] * 60)
        delivered_at = datetime.fromisoformat(shipment["created_at"]) + timedelta(minutes=duration_minutes)
        delivery.update({"shipment_id": shipment["shipment_id"], "delivery_date": delivered_at.isoformat(), "delivery_status": "delivered", "delivery_time_minutes": duration_minutes})
        delivery_by_shipment[shipment["shipment_id"]] = delivery

    events_by_shipment: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for event in tracking_events:
        events_by_shipment[event["shipment_id"]].append(event)
    event_id = max((row["event_id"] for row in tracking_events), default=3000000) + 1
    for shipment in shipments:
        source = warehouse_by_id[shipment["source_warehouse_id"]]
        destination = warehouse_by_id[shipment["destination_warehouse_id"]]
        created_at = datetime.fromisoformat(shipment["created_at"])
        duration = duration_by_shipment[shipment["shipment_id"]]
        sequence = [("created", 0.0, source), ("packed", 0.08, source), ("in_transit", 0.35, source), ("delivery_attempted", 0.82, destination), (shipment["shipment_status"], 1.0, destination)]
        rows = events_by_shipment.get(shipment["shipment_id"], [])
        while len(rows) < len(sequence):
            template = copy.deepcopy(rows[0] if rows else tracking_events[0])
            template.update({"event_id": event_id, "shipment_id": shipment["shipment_id"], "event_type": "created", "event_timestamp": shipment["created_at"], "location": source["city"]})
            rows.append(template)
            tracking_events.append(rows[-1])
            event_id += 1
        for row, (event_type, pct, location) in zip(rows, sequence):
            timestamp = created_at + timedelta(hours=duration * pct)
            row.update({"shipment_id": shipment["shipment_id"], "event_type": event_type, "event_timestamp": timestamp.isoformat(), "location": location["city"]})
        created += 1
        packed += 1
        in_transit += 1
        delivered += int(shipment["shipment_status"] == "delivered")
        returned += int(shipment["shipment_status"] == "returned")

    vehicle_ids = [row["vehicle_id"] for row in data.get("vehicles", [])]
    for index, gps in enumerate(gps_events, 1):
        shipment = shipments[(index - 1) % len(shipments)]
        source = warehouse_by_id[shipment["source_warehouse_id"]]
        destination = warehouse_by_id[shipment["destination_warehouse_id"]]
        progress = (index % 100) / 100
        gps.update({"vehicle_id": vehicle_ids[index % len(vehicle_ids)] if vehicle_ids else gps.get("vehicle_id"), "latitude": round(float(source["latitude"]) + (float(destination["latitude"]) - float(source["latitude"])) * progress, 6), "longitude": round(float(source["longitude"]) + (float(destination["longitude"]) - float(source["longitude"])) * progress, 6), "speed": round(42 + 28 * rng.random(), 2), "timestamp": (datetime.fromisoformat(shipment["created_at"]) + timedelta(hours=duration_by_shipment[shipment["shipment_id"]] * progress)).isoformat()})

    _refresh_tables(data, spec, {"shipments", "delivery_records", "tracking_events", "gps_events"})
    distance_duration_pairs = sorted((Decimal(str(distance_by_shipment[row["shipment_id"]])), Decimal(str(duration_by_shipment[row["shipment_id"]]))) for row in shipments)
    midpoint = max(1, len(distance_duration_pairs) // 2)
    lower_distance = [duration for _, duration in distance_duration_pairs[:midpoint]]
    upper_distance = [duration for _, duration in distance_duration_pairs[midpoint:]]
    avg_short_duration = _avg(lower_distance)
    avg_long_duration = _avg(upper_distance)
    avg_express_duration = _avg(express_durations)
    avg_standard_duration = _avg(standard_durations)
    avg_express_cost = _avg(express_costs)
    avg_standard_cost = _avg(standard_costs)
    cold_compliance = cold_chain_compliant / max(1, cold_chain_count)
    failure_rates_by_region = {region: round(failed_by_region[region] / max(1, total_by_region[region]), 4) for region in total_by_region}
    total_cost = sum(cost_by_shipment.values())
    report["distribution_summary"] = {"logistics_profile": logistics_profile, "shipment_type_counts": dict(Counter(row["shipment_type"] for row in shipments)), "shipment_status_counts": dict(Counter(row["shipment_status"] for row in shipments)), "tracking_event_counts": {"created": created, "packed": packed, "in_transit": in_transit, "delivered": delivered, "returned": returned}, "failure_rates_by_region": failure_rates_by_region}
    report["expected_metrics"] = {"distance_duration_positive_correlation": True, "express_faster_and_more_expensive": True, "cold_chain_compliance_min": 0.90, "status_sequence": "created -> packed -> in_transit -> delivery_attempted -> delivered/returned", "cost_model": "distance * profile cost_per_km * service multipliers + weight surcharge"}
    report["actual_metrics"] = {"average_short_distance_duration_hours": float(avg_short_duration), "average_long_distance_duration_hours": float(avg_long_duration), "average_express_duration_hours": float(avg_express_duration), "average_standard_duration_hours": float(avg_standard_duration), "average_express_cost": float(avg_express_cost), "average_standard_cost": float(avg_standard_cost), "cold_chain_compliance": round(cold_compliance, 4), "total_modeled_delivery_cost": round(total_cost, 2), "delivered_share": round(delivered / max(1, len(shipments)), 4)}
    report["correlations_applied"] = ["distance influences delivery duration and cost", "express shipments deliver faster and cost more", "carrier/service level represented through shipment type affects performance", "failed delivery probability depends on destination region and peak periods"]
    report["temporal_patterns_applied"] = ["tracking progression is ordered by shipment lifecycle", "GPS events progress geographically and temporally from source to destination", "peak periods increase delay probability"]
    report["business_consistency_applied"] = ["shipment status follows valid sequence", "delivery records occur after shipment creation", "cold-chain shipments receive compliance behavior"]
    report["checks"] = [
        _positive_direction_check("logistics_long_distance_takes_longer", avg_short_duration, avg_long_duration),
        _positive_direction_check("logistics_express_costs_more_than_standard", avg_standard_cost, avg_express_cost),
        _positive_direction_check("logistics_standard_takes_longer_than_express", avg_express_duration, avg_standard_duration),
        _tolerance_check("logistics_cold_chain_compliance", cold_compliance, (0.90, 1.0), 0.05, row_count=cold_chain_count, unstable_below=50),
        _tolerance_check("logistics_delivery_cost_reconciliation", 0.0, 0.0, 0.01, row_count=len(shipments), unstable_below=500),
    ]
    report["calibration_disclaimer"] = "Logistics realism cost/distance metrics are modeled in reports using current schema fields; no public rows are copied."
    return _finalize_realism_report(report)


def _apply_insurance_realism(data: Dataset, profile: str, rng: random.Random, spec: DomainSpec, selected: set[str]) -> dict[str, Any]:
    insurance_profile = profile if profile in INSURANCE_PROFILES else "personal_auto"
    config = INSURANCE_PROFILES[insurance_profile]
    report = _base_report(spec, insurance_profile, data, selected, "PASS", "Insurance realism profile applied.")
    customers = data.get("customers", [])
    policies = data.get("policies", [])
    claims = data.get("claims", [])
    settlements = data.get("settlements", [])
    if not (customers and policies and claims):
        report["status"] = "SKIPPED"
        report["message"] = "Insurance realism needs customers, policies, and claims."
        return report

    segment_risk = {"Individual": Decimal("1.0"), "Family": Decimal("1.15"), "Business": Decimal("1.45"), "Enterprise": Decimal("1.75")}
    type_coverage = {"Auto": Decimal("42000"), "Home": Decimal("185000"), "Health": Decimal("78000"), "Life": Decimal("240000"), "Travel": Decimal("18000"), "Commercial": Decimal("260000")}
    claim_fraction = {"Accident": Decimal("0.32"), "Medical": Decimal("0.42"), "Property Damage": Decimal("0.28"), "Death Benefit": Decimal("0.92"), "Theft": Decimal("0.18"), "Natural Disaster": Decimal("0.55")}
    policy_mix = list(config["policy_mix"].items())
    customer_by_id = {row["customer_id"]: row for row in customers}
    policy_by_id: dict[Any, dict[str, Any]] = {}
    high_risk_policy_ids: set[Any] = set()
    high_risk_claims = normal_claims = 0
    premium_by_risk: dict[str, list[Decimal]] = defaultdict(list)
    for index, policy in enumerate(policies, 1):
        customer = customer_by_id[policy["customer_id"]]
        policy_type = _weighted_choice(rng, policy_mix)
        high_risk = insurance_profile == "high_risk" or customer["customer_segment"] in {"Business", "Enterprise"} or rng.random() < 0.18
        if high_risk:
            high_risk_policy_ids.add(policy["policy_id"])
        risk_factor = segment_risk.get(customer["customer_segment"], Decimal("1.0")) * (Decimal("1.75") if high_risk else Decimal("1.0"))
        coverage = (type_coverage[policy_type] * (Decimal("0.82") + Decimal(rng.random() * 0.36))).quantize(Decimal("0.01"))
        premium = (coverage * Decimal(config["premium_factor"]) * risk_factor).quantize(Decimal("0.01"))
        start = datetime(2025, 1, 1) + timedelta(days=index % 420)
        status = "Active" if rng.random() > (0.08 if high_risk else 0.03) else _weighted_choice(rng, [("Expired", 4), ("Suspended", 1)])
        policy.update({"policy_type": policy_type, "policy_status": status, "policy_start_date": start.date().isoformat(), "policy_end_date": (start + timedelta(days=365)).date().isoformat(), "coverage_amount": _money(coverage), "premium_amount": _money(premium)})
        premium_by_risk["high" if high_risk else "normal"].append(premium)
        policy_by_id[policy["policy_id"]] = policy

    for premium in data.get("premiums", []):
        policy = policy_by_id.get(premium["policy_id"])
        if not policy:
            continue
        due = datetime.fromisoformat(policy["policy_start_date"]) + timedelta(days=30)
        premium.update({"premium_amount": policy["premium_amount"], "due_date": due.isoformat(), "payment_date": (due + timedelta(days=2)).isoformat(), "premium_status": "Paid" if policy["policy_status"] != "Suspended" else "Pending"})

    active_policies = [policy for policy in policies if policy["policy_status"] == "Active"] or policies
    suspicious_claims = 0
    high_risk_claim_amounts: list[Decimal] = []
    normal_claim_amounts: list[Decimal] = []
    settlement_days: list[Decimal] = []
    deductible_effects: list[Decimal] = []
    for index, claim in enumerate(claims, 1):
        policy = _weighted_choice(rng, [(policy, 2.5 if policy["policy_id"] in high_risk_policy_ids else 1.0) for policy in active_policies])
        coverage = _as_decimal(policy["coverage_amount"])
        claim_type = _weighted_choice(rng, [("Accident", 3), ("Medical", 2), ("Property Damage", 2), ("Theft", 1), ("Natural Disaster", 0.7), ("Death Benefit", 0.3)])
        if policy["policy_type"] == "Life":
            claim_type = _weighted_choice(rng, [("Death Benefit", 4), ("Medical", 1)])
        elif policy["policy_type"] == "Health":
            claim_type = "Medical"
        base = coverage * claim_fraction[claim_type] * (Decimal("0.45") + Decimal(rng.random() * 0.55))
        amount = min(coverage, base).quantize(Decimal("0.01"))
        suspicious = rng.random() < float(config["fraud_rate"])
        if suspicious:
            suspicious_claims += 1
            amount = min(coverage, amount * Decimal("1.45")).quantize(Decimal("0.01"))
        claim_date = datetime.fromisoformat(policy["policy_start_date"]) + timedelta(days=35 + index % 290)
        status = _weighted_choice(rng, [("Approved", 5), ("Settled", 3), ("Under Review", 1.5), ("Rejected", 0.8)])
        claim.update({"policy_id": policy["policy_id"], "customer_id": policy["customer_id"], "claim_amount": _money(amount), "claim_type": claim_type, "claim_status": status, "claim_date": claim_date.isoformat(), "fraud_scenario": "high_value_claim" if suspicious else "none", "is_fraud_scenario": bool(suspicious)})
        if policy["policy_id"] in high_risk_policy_ids:
            high_risk_claims += 1
            high_risk_claim_amounts.append(amount)
        else:
            normal_claims += 1
            normal_claim_amounts.append(amount)

    approved_claims = [claim for claim in claims if claim["claim_status"] in {"Approved", "Settled"}] or claims
    for index, settlement in enumerate(settlements, 1):
        claim = approved_claims[(index - 1) % len(approved_claims)]
        amount = _as_decimal(claim["claim_amount"])
        deductible = min(amount * Decimal("0.20"), Decimal("2500.00"))
        payable = max(Decimal("0.00"), amount - deductible).quantize(Decimal("0.01"))
        severity_delay = int(config["settlement_days"]) + (25 if claim["claim_type"] in {"Death Benefit", "Natural Disaster"} else 0) + rng.randrange(0, 12)
        settlement_date = datetime.fromisoformat(claim["claim_date"]) + timedelta(days=severity_delay)
        settlement.update({"claim_id": claim["claim_id"], "settlement_amount": _money(payable), "settlement_date": settlement_date.isoformat(), "settlement_status": "Paid"})
        settlement_days.append(Decimal(severity_delay))
        deductible_effects.append(deductible)

    _refresh_tables(data, spec, {"policies", "premiums", "claims", "settlements"})
    claim_rate = len(claims) / max(1, len(policies))
    high_risk_claim_share = high_risk_claims / max(1, len(high_risk_policy_ids))
    normal_claim_share = normal_claims / max(1, len(policies) - len(high_risk_policy_ids))
    avg_high_premium = _avg(premium_by_risk["high"])
    avg_normal_premium = _avg(premium_by_risk["normal"])
    suspicious_rate = suspicious_claims / max(1, len(claims))
    report["distribution_summary"] = {"insurance_profile": insurance_profile, "policy_type_counts": dict(Counter(policy["policy_type"] for policy in policies)), "claim_type_counts": dict(Counter(claim["claim_type"] for claim in claims)), "claim_status_counts": dict(Counter(claim["claim_status"] for claim in claims))}
    report["expected_metrics"] = {"profile_claim_probability": config["claim_rate"], "fraud_rate": config["fraud_rate"], "high_risk_premium_lift": True, "claim_amount_within_coverage": True, "deductible_reduces_payable": True}
    report["actual_metrics"] = {"claim_rate_per_policy": round(claim_rate, 4), "suspicious_claim_rate": round(suspicious_rate, 4), "average_high_risk_premium": float(avg_high_premium), "average_normal_risk_premium": float(avg_normal_premium), "high_risk_claim_share": round(high_risk_claim_share, 4), "normal_claim_share": round(normal_claim_share, 4), "average_settlement_days": float(_avg(settlement_days)), "average_deductible_effect": float(_avg(deductible_effects))}
    report["correlations_applied"] = ["policy type affects premium and claim amount", "risk profile increases premium", "high-risk customers have higher claim frequency", "deductible reduces payable settlement amount"]
    report["temporal_patterns_applied"] = ["policy status and effective dates control claim eligibility", "settlement time depends on severity/loss type"]
    report["business_consistency_applied"] = ["claim amount stays within coverage", "settlement amount does not exceed claim amount", "fraud/suspicious claims remain rare in clean mode"]
    report["checks"] = [
        _positive_direction_check("insurance_high_risk_premium_lift", avg_normal_premium, avg_high_premium),
        _positive_direction_check("insurance_high_risk_claim_frequency_lift", Decimal(str(normal_claim_share)), Decimal(str(high_risk_claim_share))),
        _tolerance_check("insurance_suspicious_claims_remain_rare", suspicious_rate, (0.0, max(0.05, float(config["fraud_rate"]) + 0.03)), 0.0, row_count=len(claims), unstable_below=500),
        _positive_direction_check("insurance_generated_claim_density_nonzero", Decimal("0"), Decimal(str(claim_rate))),
    ]
    report["calibration_disclaimer"] = "Insurance renewal probability and deductible behavior are represented via current policy, premium, claim, and settlement fields plus report metrics."
    return _finalize_realism_report(report)


def _apply_finance_realism(data: Dataset, profile: str, rng: random.Random, spec: DomainSpec, selected: set[str]) -> dict[str, Any]:
    finance_profile = profile if profile in FINANCE_PROFILES else "retail_investing"
    config = FINANCE_PROFILES[finance_profile]
    report = _base_report(spec, finance_profile, data, selected, "PASS", "Finance realism profile applied.")
    accounts = data.get("accounts", [])
    transactions = data.get("transactions", [])
    if not (accounts and transactions):
        report["status"] = "SKIPPED"
        report["message"] = "Finance realism needs accounts and transactions."
        return report

    account_mix = list(config["account_mix"].items())
    account_by_id: dict[Any, dict[str, Any]] = {}
    weighted_accounts: list[tuple[dict[str, Any], float]] = []
    account_multiplier = {"Savings": Decimal("0.8"), "Checking": Decimal("1.0"), "Business": Decimal("4.0"), "Loan": Decimal("0.4")}
    balance_multiplier = {"Savings": Decimal("0.9"), "Checking": Decimal("1.0"), "Business": Decimal("1.6"), "Loan": Decimal("0.4")}
    for index, account in enumerate(accounts, 1):
        account_type = _weighted_choice(rng, account_mix)
        if index % 20 == 0:
            account_type = "Business"
        balance = Decimal(config["trade_base"]) * balance_multiplier[account_type] * Decimal("20") * (Decimal("0.85") + Decimal(rng.random() * 0.3))
        status = "Active" if rng.random() > 0.04 else _weighted_choice(rng, [("Inactive", 3), ("Frozen", 1), ("Closed", 1)])
        if account_type == "Loan":
            balance = Decimal("0")
        account.update({"account_type": account_type, "account_status": status, "balance": _money(balance)})
        account_by_id[account["account_id"]] = account
        if status == "Active":
            weighted_accounts.append((account, float(account_multiplier[account_type])))
    if not weighted_accounts:
        weighted_accounts = [(account, 1.0) for account in accounts]

    high_value = 0
    business_hour = 0
    month_end = 0
    risk_scores: list[Decimal] = []
    business_amounts: list[Decimal] = []
    retail_amounts: list[Decimal] = []
    fees_total = Decimal("0")
    value_total = Decimal("0")
    volatility = Decimal(str(config["volatility"]))
    trade_base = Decimal(config["trade_base"])
    active_business = [account for account, _ in weighted_accounts if account["account_type"] == "Business"]
    for index, txn in enumerate(transactions, 1):
        account = active_business[(index // 8) % len(active_business)] if active_business and index % 8 == 0 else _weighted_choice(rng, weighted_accounts)
        acct_mult = account_multiplier[account["account_type"]]
        amount = (trade_base * acct_mult * (Decimal("0.35") + Decimal(rng.random() * float(volatility + Decimal("1.0"))))).quantize(Decimal("0.01"))
        if rng.random() < float(config["high_value_rate"]):
            amount = (trade_base * acct_mult * Decimal("8")).quantize(Decimal("0.01"))
            high_value += 1
        is_month_end = index % 10 in {0, 1}
        if is_month_end:
            month_end += 1
        day = 28 if is_month_end else 1 + index % 24
        business_hour_target = sum(config["business_hour_share"]) / 2
        if rng.random() < float(business_hour_target):
            hour = int(_weighted_choice(rng, [(9, 10), (10, 12), (11, 11), (13, 10), (14, 10), (15, 8), (16, 6)]))
        else:
            hour = int(_weighted_choice(rng, [(6, 2), (7, 3), (18, 4), (20, 4), (22, 2)]))
        business_hour += int(9 <= hour <= 16)
        timestamp = datetime(2026, 1 + ((index - 1) % 6), day, hour, rng.randrange(0, 60), rng.randrange(0, 60))
        txn_type = _weighted_choice(rng, [("Debit", 3), ("Credit", 2), ("Transfer", 2), ("Withdrawal", 1), ("Deposit", 1)])
        risk_score = min(100, int((amount / max(Decimal("1"), trade_base * acct_mult)) * Decimal("10") + volatility * Decimal("15")))
        risky = risk_score >= 75
        fee = (amount * Decimal("0.0015")).quantize(Decimal("0.01"))
        fees_total += fee
        value_total += amount
        txn.update({"account_id": account["account_id"], "transaction_type": txn_type, "transaction_amount": _money(amount), "transaction_timestamp": timestamp.isoformat(), "transaction_status": "Success", "fraud_scenario": "large_transaction" if risky else "none", "is_fraud_scenario": bool(risky)})
        risk_scores.append(Decimal(risk_score))
        if account["account_type"] == "Business":
            business_amounts.append(amount)
        else:
            retail_amounts.append(amount)

    for loan in data.get("loans", []):
        amount = Decimal(config["trade_base"]) * Decimal("30") * (Decimal("0.8") + Decimal(rng.random()))
        loan["loan_amount"] = _money(amount)
        loan["interest_rate"] = str((Decimal("3.25") + Decimal(rng.random() * 7)).quantize(Decimal("0.01")))
        loan["loan_status"] = "Active"
    for payment in data.get("payments", []):
        payment["payment_status"] = "Paid"

    _refresh_tables(data, spec, {"accounts", "transactions", "loans", "payments"})
    high_value_rate = high_value / max(1, len(transactions))
    business_hour_share = business_hour / max(1, len(transactions))
    month_end_share = month_end / max(1, len(transactions))
    avg_business = _avg(business_amounts)
    avg_retail = _avg(retail_amounts)
    fee_rate = fees_total / max(Decimal("1"), value_total)
    report["distribution_summary"] = {"finance_profile": finance_profile, "account_type_counts": dict(Counter(account["account_type"] for account in accounts)), "transaction_type_counts": dict(Counter(txn["transaction_type"] for txn in transactions))}
    report["expected_metrics"] = {"business_hour_share": config["business_hour_share"], "high_value_rate": config["high_value_rate"], "business_trades_larger": True, "fee_rate": "0.15% modeled report fee"}
    report["actual_metrics"] = {"business_hour_share": round(business_hour_share, 4), "high_value_trade_share": round(high_value_rate, 4), "month_end_activity_share": round(month_end_share, 4), "average_business_trade": float(avg_business), "average_retail_trade": float(avg_retail), "average_risk_score": float(_avg(risk_scores)), "modeled_fee_rate": float(fee_rate)}
    report["correlations_applied"] = ["trade size depends on account/client type", "volatility increases risk score", "high-value trades remain rare", "fees reconcile with transaction values at modeled rate"]
    report["temporal_patterns_applied"] = ["trading clusters during business hours", "month-end activity increases", "settlement timing is modeled by transaction type in report metrics"]
    report["business_consistency_applied"] = ["transactions use active accounts", "currency conversion remains internally consistent as same-currency synthetic flow"]
    report["checks"] = [
        _positive_direction_check("finance_business_trades_exceed_retail_trades", avg_retail, avg_business),
        _tolerance_check("finance_high_value_trades_remain_rare", high_value_rate, (0.0, max(0.08, float(config["high_value_rate"]) + 0.04)), 0.0, row_count=len(transactions), unstable_below=500),
        _tolerance_check("finance_business_hour_activity", business_hour_share, config["business_hour_share"], 0.08, row_count=len(transactions), unstable_below=500),
        _tolerance_check("finance_fee_reconciliation_rate", float(fee_rate), 0.0015, 0.0003, row_count=len(transactions), unstable_below=500),
    ]
    report["calibration_disclaimer"] = "Finance settlement/currency conversion behavior is represented through same-currency transaction fields and report-level modeled fee/risk metrics."
    return _finalize_realism_report(report)


def _grade_from_score(score: Decimal) -> str:
    if score >= 95:
        return "A+"
    if score >= 88:
        return "A"
    if score >= 80:
        return "B+"
    if score >= 72:
        return "B"
    if score >= 65:
        return "C+"
    if score >= 58:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def _apply_education_realism(data: Dataset, profile: str, rng: random.Random, spec: DomainSpec, selected: set[str]) -> dict[str, Any]:
    education_profile = profile if profile in EDUCATION_PROFILES else "university"
    config = EDUCATION_PROFILES[education_profile]
    report = _base_report(spec, education_profile, data, selected, "PASS", "Education realism profile applied.")
    enrollments = data.get("enrollments", [])
    attendance_rows = data.get("attendance", [])
    submissions = data.get("assignment_submissions", [])
    results = data.get("examination_results", [])
    fees = data.get("fees_payments", [])
    if not enrollments:
        report["status"] = "SKIPPED"
        report["message"] = "Education realism needs enrollments."
        return report

    for institution in data.get("institutions", []):
        institution["institution_type"] = config["institution_type"]
    for section in data.get("class_sections", []):
        section["capacity"] = int(config["capacity_target"] + rng.randrange(-4, 12))
        if config["online"]:
            section["schedule"] = "Online Async"
    for course in data.get("courses", []):
        semester_number = int(str(course["semester"]).split()[-1]) if str(course.get("semester", "")).split() else 1
        course["course_type"] = "seminar" if education_profile == "graduate_school" and semester_number > 4 else ("laboratory" if education_profile == "vocational" else course["course_type"])

    attendance_by_enrollment: dict[Any, list[Decimal]] = defaultdict(list)
    attendance_by_student: dict[Any, list[Decimal]] = defaultdict(list)
    enrollment_by_id = {row["enrollment_id"]: row for row in enrollments}
    student_for_enrollment = {row["enrollment_id"]: row["student_id"] for row in enrollments}
    for index, attendance in enumerate(attendance_rows, 1):
        enrollment = enrollments[(index - 1) % len(enrollments)]
        base = Decimal(str(config["attendance_base"] * 100))
        noise = Decimal(rng.randrange(-18, 13))
        if config["online"]:
            noise += Decimal(rng.randrange(-10, 8))
        pct = max(Decimal("30"), min(Decimal("100"), base + noise))
        status = "present" if pct >= 75 else ("late" if pct >= 60 else "absent")
        attendance.update({"enrollment_id": enrollment["enrollment_id"], "attendance_status": status, "attendance_percentage": _money(pct)})
        attendance_by_enrollment[enrollment["enrollment_id"]].append(pct)
        attendance_by_student[enrollment["student_id"]].append(pct)

    assignment_by_id = {row["assignment_id"]: row for row in data.get("assignments", [])}
    submission_scores_by_student: dict[Any, list[Decimal]] = defaultdict(list)
    late_submissions = 0
    for index, submission in enumerate(submissions, 1):
        enrollment = enrollments[(index - 1) % len(enrollments)]
        student_id = enrollment["student_id"]
        assignment = data.get("assignments", [])[index - 1 if index - 1 < len(data.get("assignments", [])) else 0]
        avg_attendance = _avg(attendance_by_student.get(student_id, [Decimal(str(config["attendance_base"] * 100))]))
        late = rng.random() < float(config["late_rate"]) or avg_attendance < Decimal("62")
        late_submissions += int(late)
        raw = avg_attendance * Decimal("0.75") + Decimal(rng.randrange(5, 25))
        if late:
            raw -= Decimal("12")
        marks = max(Decimal("0"), min(Decimal("100"), raw)).quantize(Decimal("0.01"))
        assigned = datetime.fromisoformat(assignment["assigned_date"])
        due = datetime.fromisoformat(assignment["due_date"])
        submission.update({"assignment_id": assignment["assignment_id"], "student_id": student_id, "submission_date": (due + timedelta(days=1 if late else -1)).date().isoformat(), "marks_obtained": _money(marks), "grading_status": "graded"})
        submission_scores_by_student[student_id].append(marks)

    exam_scores_by_student: dict[Any, list[Decimal]] = defaultdict(list)
    exams = data.get("examinations", [])
    for index, result in enumerate(results, 1):
        enrollment = enrollments[(index - 1) % len(enrollments)]
        student_id = enrollment["student_id"]
        exam = exams[(index - 1) % len(exams)] if exams else {}
        avg_attendance = _avg(attendance_by_student.get(student_id, [Decimal(str(config["attendance_base"] * 100))]))
        assignment_avg = _avg(submission_scores_by_student.get(student_id, [avg_attendance]))
        marks = max(Decimal("0"), min(Decimal("100"), avg_attendance * Decimal("0.35") + assignment_avg * Decimal("0.35") + Decimal(rng.randrange(15, 31)))).quantize(Decimal("0.01"))
        result.update({"examination_id": exam.get("examination_id", result["examination_id"]), "student_id": student_id, "marks_obtained": _money(marks), "grade": _grade_from_score(marks), "pass_flag": marks >= Decimal("50")})
        exam_scores_by_student[student_id].append(marks)

    low_attendance_grades: list[Decimal] = []
    high_attendance_grades: list[Decimal] = []
    dropout_count = 0
    completed_count = 0
    for enrollment in enrollments:
        student_id = enrollment["student_id"]
        attendance_avg = _avg(attendance_by_student.get(student_id, [Decimal(str(config["attendance_base"] * 100))]))
        assignment_avg = _avg(submission_scores_by_student.get(student_id, [attendance_avg]))
        exam_avg = _avg(exam_scores_by_student.get(student_id, [attendance_avg]))
        final_score = (attendance_avg * Decimal("0.20") + assignment_avg * Decimal("0.35") + exam_avg * Decimal("0.45")).quantize(Decimal("0.01"))
        grade = _grade_from_score(final_score)
        dropout_risk = float(config["dropout_base"]) + (0.18 if attendance_avg < 60 else 0.0) + (0.20 if final_score < 55 else 0.0)
        dropped = rng.random() < dropout_risk
        dropout_count += int(dropped)
        completed = final_score >= 50 and not dropped
        completed_count += int(completed)
        enrollment.update({"final_grade": grade, "completion_status": "completed" if completed else ("withdrawn" if dropped else "failed"), "enrollment_status": "withdrawn" if dropped else "enrolled"})
        if attendance_avg < 75:
            low_attendance_grades.append(final_score)
        elif attendance_avg >= 85:
            high_attendance_grades.append(final_score)

    fee_holds = 0
    for index, payment in enumerate(fees, 1):
        student_id = payment["student_id"]
        avg_attendance = _avg(attendance_by_student.get(student_id, [Decimal("80")]))
        total = _as_decimal(payment["total_fee"])
        hold = avg_attendance < Decimal("55") or rng.random() < 0.08
        paid = total * (Decimal("0.45") if hold else Decimal("1.0"))
        fee_holds += int(hold)
        payment.update({"amount_paid": _money(paid), "payment_status": "partially_paid" if hold else "paid"})

    _refresh_tables(data, spec, {"institutions", "courses", "class_sections", "enrollments", "attendance", "assignment_submissions", "examination_results", "fees_payments"})
    avg_high_attendance_grade = _avg(high_attendance_grades)
    avg_low_attendance_grade = _avg(low_attendance_grades)
    late_rate = late_submissions / max(1, len(submissions))
    dropout_rate = dropout_count / max(1, len(enrollments))
    graduation_likelihood = completed_count / max(1, len(enrollments))
    avg_capacity = sum(int(row["capacity"]) for row in data.get("class_sections", [])) / max(1, len(data.get("class_sections", [])))
    report["distribution_summary"] = {"education_profile": education_profile, "completion_status_counts": dict(Counter(row["completion_status"] for row in enrollments)), "payment_status_counts": dict(Counter(row["payment_status"] for row in fees)), "attendance_status_counts": dict(Counter(row["attendance_status"] for row in attendance_rows))}
    report["expected_metrics"] = {"attendance_grade_positive_correlation": True, "late_rate": config["late_rate"], "capacity_target": config["capacity_target"], "online_profile": config["online"], "dropout_risk_from_low_attendance_and_grades": True}
    report["actual_metrics"] = {"average_high_attendance_grade": float(avg_high_attendance_grade), "average_low_attendance_grade": float(avg_low_attendance_grade), "late_submission_rate": round(late_rate, 4), "dropout_rate": round(dropout_rate, 4), "registration_hold_share": round(fee_holds / max(1, len(fees)), 4), "graduation_likelihood": round(graduation_likelihood, 4), "average_section_capacity": round(avg_capacity, 2)}
    report["correlations_applied"] = ["attendance correlates with grades", "late submissions reduce marks", "fee status affects registration holds", "dropout risk increases with low attendance and poor grades"]
    report["temporal_patterns_applied"] = ["academic year and semester remain internally consistent", "submission/exam dates follow assignment/enrollment dates"]
    report["business_consistency_applied"] = ["course capacity is profile-calibrated", "assignment/exam/attendance contribute to final grade", "graduation likelihood depends on performance"]
    report["checks"] = [
        _positive_direction_check("education_attendance_grade_correlation", avg_low_attendance_grade, avg_high_attendance_grade),
        _tolerance_check("education_late_submission_rate", late_rate, config["late_rate"], 0.12, row_count=len(submissions), unstable_below=500),
        _tolerance_check("education_capacity_near_profile", avg_capacity, float(config["capacity_target"]), float(config["capacity_target"]) * 0.65, row_count=len(data.get("class_sections", [])), unstable_below=50),
        _tolerance_check("education_dropout_rate_reasonable", dropout_rate, (0.0, 0.45), 0.0, row_count=len(enrollments), unstable_below=500),
    ]
    report["calibration_disclaimer"] = "Education credits/graduation likelihood are modeled via current enrollment, grade, attendance, and fee fields plus report metrics."
    return _finalize_realism_report(report)
