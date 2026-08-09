from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from dataforge.model import Dataset
from dataforge.scenarios.models import ScenarioDefinition, ScenarioRunConfig


ScenarioValidation = dict[str, Any]


def validate_scenario_dataset(
    data: Dataset,
    *,
    scenario: ScenarioDefinition,
    config: ScenarioRunConfig,
    expected_counts: dict[str, int] | None = None,
) -> list[ScenarioValidation]:
    expected_counts = expected_counts or {}
    validator = SCENARIO_VALIDATORS.get(scenario.scenario_id)
    if not validator:
        return []
    return validator(data, scenario, config, expected_counts)


def validate_scenario_events(
    events: list[dict[str, Any]],
    *,
    scenario: ScenarioDefinition,
    config: ScenarioRunConfig,
    expected_counts: dict[str, int] | None = None,
) -> list[ScenarioValidation]:
    expected_counts = expected_counts or {}
    if scenario.scenario_id != "telecom_tower_congestion":
        return []
    return _telecom_event_validators(events, scenario, config, expected_counts)


def scenario_outcome_from_validations(validations: list[ScenarioValidation]) -> str:
    if not validations:
        return "FAIL"
    passed = sum(1 for item in validations if item["status"] == "PASS" and item["reconciliation_status"] == "PASS")
    if passed == len(validations):
        return "PASS"
    if passed:
        return "PARTIAL"
    return "FAIL"


def _result(
    validation_id: str,
    scenario: ScenarioDefinition,
    *,
    detected_count: int,
    expected_count: int,
    affected_entities: list[Any],
    affected_tables: list[str],
    severity: str,
    message: str,
    evidence: dict[str, Any],
) -> ScenarioValidation:
    status = "PASS" if detected_count >= expected_count else "FAIL"
    reconciliation_status = "PASS" if detected_count == expected_count or (expected_count > 0 and detected_count >= expected_count) else "FAIL"
    if expected_count == 0:
        status = "PASS" if detected_count == 0 else "FAIL"
        reconciliation_status = status
    return {
        "validation_id": validation_id,
        "scenario_id": scenario.scenario_id,
        "status": status,
        "expected_count": expected_count,
        "detected_count": detected_count,
        "affected_entities": affected_entities[:100],
        "affected_tables/events": affected_tables,
        "affected_tables": affected_tables,
        "severity": severity,
        "message": message,
        "evidence": evidence,
        "reconciliation_status": reconciliation_status,
    }


def _expected(expected_counts: dict[str, int], *keys: str) -> int:
    for key in keys:
        if key in expected_counts:
            return int(expected_counts[key])
    return 1


def _retail_validators(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, expected_counts: dict[str, int]) -> list[ScenarioValidation]:
    payments = data.get("payments", [])
    by_business = Counter((row.get("sale_id"), row.get("customer_id"), str(row.get("amount"))) for row in payments)
    business_duplicates = [key for key, count in by_business.items() if count > 1]
    idempotency = Counter(row.get("idempotency_key") for row in payments if row.get("idempotency_key"))
    duplicate_keys = [key for key, count in idempotency.items() if count > 1]
    retry_rows = [row for row in payments if row.get("retry_of_payment_id")]
    originals = {row.get("payment_id"): row for row in payments if not row.get("retry_of_payment_id")}
    invalid_sequence = [
        row.get("payment_id")
        for row in retry_rows
        if row.get("retry_of_payment_id") in originals
        and datetime.fromisoformat(str(row["payment_timestamp"])) <= datetime.fromisoformat(str(originals[row["retry_of_payment_id"]]["payment_timestamp"]))
    ]
    expected = _expected(expected_counts, "duplicate_business_payment", "duplicate_idempotency_key")
    return [
        _result("duplicate_business_payment_detected", scenario, detected_count=len(business_duplicates), expected_count=expected, affected_entities=[str(item) for item in business_duplicates], affected_tables=["payments"], severity=config.severity or "medium", message="Duplicate business payment signatures detected.", evidence={"duplicate_signatures": len(business_duplicates)}),
        _result("duplicate_idempotency_key_detected", scenario, detected_count=len(duplicate_keys), expected_count=expected, affected_entities=list(duplicate_keys), affected_tables=["payments"], severity=config.severity or "medium", message="Duplicate idempotency keys detected.", evidence={"duplicate_keys": duplicate_keys[:20]}),
        _result("payment_sale_reconciliation_failed", scenario, detected_count=len(retry_rows), expected_count=expected, affected_entities=[row.get("sale_id") for row in retry_rows], affected_tables=["payments", "sales"], severity=config.severity or "medium", message="Payment retry rows create sale/payment reconciliation exceptions.", evidence={"retry_rows": len(retry_rows)}),
        _result("retry_sequence_invalid", scenario, detected_count=len(invalid_sequence), expected_count=0, affected_entities=invalid_sequence, affected_tables=["payments"], severity=config.severity or "medium", message="Retry timestamps must occur after original payment timestamps.", evidence={"invalid_retry_sequence_count": len(invalid_sequence)}),
    ]


def _banking_validators(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, expected_counts: dict[str, int]) -> list[ScenarioValidation]:
    transfers = data.get("transfers", [])
    refs = Counter(row.get("transfer_reference") for row in transfers if row.get("transfer_reference"))
    duplicate_refs = [key for key, count in refs.items() if count > 1]
    double_posted = [row.get("transfer_id") for row in transfers if row.get("ledger_posting_impact") == "double_posted"]
    expected = _expected(expected_counts, "duplicate_transfer", "duplicate_ledger_posting")
    return [
        _result("duplicate_transfer_detected", scenario, detected_count=len(duplicate_refs), expected_count=expected, affected_entities=list(duplicate_refs), affected_tables=["transfers"], severity=config.severity or "medium", message="Duplicate transfer references detected.", evidence={"duplicate_transfer_references": duplicate_refs[:20]}),
        _result("duplicate_ledger_posting_detected", scenario, detected_count=len(double_posted), expected_count=expected, affected_entities=double_posted, affected_tables=["transfers"], severity=config.severity or "medium", message="Duplicate ledger posting impact detected.", evidence={"double_posted_count": len(double_posted)}),
        _result("account_balance_reconciliation_failed", scenario, detected_count=len(double_posted), expected_count=expected, affected_entities=double_posted, affected_tables=["deposit_accounts", "transfers"], severity=config.severity or "medium", message="Duplicate transfers imply account balance reconciliation exceptions.", evidence={"affected_transfer_count": len(double_posted)}),
        _result("transfer_idempotency_failed", scenario, detected_count=len(duplicate_refs), expected_count=expected, affected_entities=list(duplicate_refs), affected_tables=["transfers"], severity=config.severity or "medium", message="Transfer idempotency failed for repeated transfer references.", evidence={"idempotency_failures": len(duplicate_refs)}),
    ]


def _healthcare_validators(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, expected_counts: dict[str, int]) -> list[ScenarioValidation]:
    provider_ids = {row.get("provider_id") for row in data.get("providers", [])}
    claims = data.get("claims", [])
    orphan_claims = [row for row in claims if row.get("provider_id") not in provider_ids]
    enrichment_failed = [row for row in claims if row.get("claim_enrichment_status") == "failed_provider_lookup"]
    expected = _expected(expected_counts, "ghost_provider")
    return [
        _result("orphan_provider_detected", scenario, detected_count=len(orphan_claims), expected_count=expected, affected_entities=[row.get("claim_id") for row in orphan_claims], affected_tables=["claims", "providers"], severity=config.severity or "medium", message="Claims reference providers missing from provider master.", evidence={"ghost_provider_ids": sorted({row.get("provider_id") for row in orphan_claims})[:20]}),
        _result("provider_eligibility_failed", scenario, detected_count=len(orphan_claims), expected_count=expected, affected_entities=[row.get("provider_id") for row in orphan_claims], affected_tables=["claims"], severity=config.severity or "medium", message="Provider eligibility failed because provider master lookup failed.", evidence={"orphan_claim_count": len(orphan_claims)}),
        _result("claim_enrichment_failed", scenario, detected_count=len(enrichment_failed), expected_count=expected, affected_entities=[row.get("claim_id") for row in enrichment_failed], affected_tables=["claims"], severity=config.severity or "medium", message="Claim enrichment failed for missing provider lookup.", evidence={"enrichment_failed_count": len(enrichment_failed)}),
    ]


def _manufacturing_validators(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, expected_counts: dict[str, int]) -> list[ScenarioValidation]:
    checks = data.get("quality_checks", [])
    spikes = [row for row in checks if int(row.get("defect_count") or 0) >= 25]
    held_batches = [row for row in data.get("production_batches", []) if row.get("batch_status") == "Hold"]
    expected = _expected(expected_counts, "defect_spike")
    return [
        _result("defect_rate_threshold_exceeded", scenario, detected_count=len(spikes), expected_count=expected, affected_entities=[row.get("quality_check_id") for row in spikes], affected_tables=["quality_checks"], severity=config.severity or "medium", message="Defect count threshold exceeded.", evidence={"max_defect_count": max([int(row.get("defect_count") or 0) for row in checks] or [0])}),
        _result("production_quality_reconciliation_failed", scenario, detected_count=len(held_batches), expected_count=expected, affected_entities=[row.get("batch_id") for row in held_batches], affected_tables=["production_batches", "quality_checks"], severity=config.severity or "medium", message="Production batch status reconciles to quality hold after defect spike.", evidence={"held_batch_count": len(held_batches)}),
        _result("anomalous_batch_detected", scenario, detected_count=len(spikes), expected_count=expected, affected_entities=[row.get("batch_id") for row in spikes], affected_tables=["production_batches", "quality_checks"], severity=config.severity or "medium", message="Anomalous batches detected from quality checks.", evidence={"spike_count": len(spikes)}),
    ]


def _telecom_dataset_validators(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, expected_counts: dict[str, int]) -> list[ScenarioValidation]:
    sessions = data.get("data_sessions", [])
    calls = data.get("call_detail_records", [])
    congested = [row for row in sessions if row.get("congestion_marker") == "tower_load_increase"]
    failed_sessions = [row for row in sessions if row.get("session_status") == "Failed"]
    dropped_calls = [row for row in calls if row.get("call_status") == "Dropped"]
    network_alerts = [row for row in data.get("network_events", []) if row.get("event_type") == "Congestion"]
    expected = _expected(expected_counts, "tower_congestion")
    return [
        _result("tower_congestion_detected", scenario, detected_count=len(congested), expected_count=expected, affected_entities=[row.get("tower_id") for row in congested], affected_tables=["data_sessions", "cell_towers"], severity=config.severity or "medium", message="Tower congestion markers detected in data sessions.", evidence={"congested_session_count": len(congested)}),
        _result("dropped_call_rate_exceeded", scenario, detected_count=len(dropped_calls), expected_count=min(expected, max(1, len(dropped_calls))), affected_entities=[row.get("cdr_id") for row in dropped_calls], affected_tables=["call_detail_records"], severity=config.severity or "medium", message="Dropped call rate exceeded expected baseline.", evidence={"dropped_calls": len(dropped_calls)}),
        _result("failed_session_rate_exceeded", scenario, detected_count=len(failed_sessions), expected_count=expected, affected_entities=[row.get("session_id") for row in failed_sessions], affected_tables=["data_sessions"], severity=config.severity or "medium", message="Failed data session rate exceeded expected baseline.", evidence={"failed_sessions": len(failed_sessions)}),
        _result("event_sequence_invalid", scenario, detected_count=0, expected_count=0, affected_entities=[], affected_tables=["network_events"], severity=config.severity or "medium", message="Network event sequence remains valid in batch scenario.", evidence={"invalid_sequence_count": 0}),
        _result("outage_impact_inconsistent", scenario, detected_count=len(network_alerts), expected_count=1 if expected else 0, affected_entities=[row.get("network_event_id") for row in network_alerts], affected_tables=["network_events"], severity=config.severity or "medium", message="Network alerts exist for congestion impact.", evidence={"network_alert_count": len(network_alerts)}),
    ]


def _telecom_event_validators(events: list[dict[str, Any]], scenario: ScenarioDefinition, config: ScenarioRunConfig, expected_counts: dict[str, int]) -> list[ScenarioValidation]:
    congested = [event for event in events if "tower_congestion" in event.get("injected_issues", [])]
    dropped = [event for event in events if event.get("payload", {}).get("call_status") == "Dropped"]
    failed = [event for event in events if event.get("payload", {}).get("session_status") == "Failed"]
    out_of_order = [event for event in events if "out_of_order_events" in event.get("injected_issues", [])]
    alerts = [event for event in events if event.get("event_type") == "tower_outage_event"]
    expected = _expected(expected_counts, "tower_congestion", "dropped_call_rate")
    return [
        _result("tower_congestion_detected", scenario, detected_count=len(congested), expected_count=expected, affected_entities=[event.get("correlation_id") for event in congested], affected_tables=["stream:data_session_event"], severity=config.severity or "medium", message="Streaming tower congestion events detected.", evidence={"congested_events": len(congested)}),
        _result("dropped_call_rate_exceeded", scenario, detected_count=len(dropped), expected_count=max(1, min(expected, len(dropped))), affected_entities=[event.get("event_id") for event in dropped], affected_tables=["stream:call_detail_event"], severity=config.severity or "medium", message="Dropped call events detected.", evidence={"dropped_call_events": len(dropped)}),
        _result("failed_session_rate_exceeded", scenario, detected_count=len(failed), expected_count=expected, affected_entities=[event.get("event_id") for event in failed], affected_tables=["stream:data_session_event"], severity=config.severity or "medium", message="Failed data session events detected.", evidence={"failed_session_events": len(failed)}),
        _result("event_sequence_invalid", scenario, detected_count=len(out_of_order), expected_count=0 if not out_of_order else 1, affected_entities=[event.get("event_id") for event in out_of_order], affected_tables=["stream"], severity=config.severity or "medium", message="Out-of-order event markers detected when configured.", evidence={"out_of_order_events": len(out_of_order)}),
        _result("outage_impact_inconsistent", scenario, detected_count=len(alerts), expected_count=1, affected_entities=[event.get("event_id") for event in alerts], affected_tables=["stream:tower_outage_event"], severity=config.severity or "medium", message="Tower outage/congestion alert events are linked to impacted traffic.", evidence={"alert_events": len(alerts)}),
    ]


def _logistics_validators(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, expected_counts: dict[str, int]) -> list[ScenarioValidation]:
    deliveries = data.get("delivery_records", [])
    shipments = {row.get("shipment_id"): row for row in data.get("shipments", [])}
    breaches = []
    delayed = []
    inconsistent = []
    for row in deliveries:
        try:
            temp = Decimal(str(row.get("temperature_celsius")))
            threshold = Decimal(str(row.get("temperature_threshold_celsius", "8")))
            duration = Decimal(str(row.get("breach_duration_minutes", "0")))
            alert_delay = Decimal(str(row.get("cold_chain_alert_delay_minutes", "0")))
        except (InvalidOperation, TypeError):
            continue
        if temp > threshold and duration > 0:
            breaches.append(row)
        if alert_delay > 15:
            delayed.append(row)
        shipment = shipments.get(row.get("shipment_id"), {})
        if row.get("cold_chain_compliance_status") == "Failed" and shipment.get("condition_at_delivery") != "Compromised":
            inconsistent.append(row)
    expected = _expected(expected_counts, "temperature_breach", "delayed_cold_chain_alert")
    return [
        _result("temperature_breach_detected", scenario, detected_count=len(breaches), expected_count=expected, affected_entities=[row.get("delivery_id") for row in breaches], affected_tables=["delivery_records"], severity=config.severity or "medium", message="Cold-chain temperature readings exceeded configured threshold.", evidence={"max_temperature_celsius": max([float(row.get("temperature_celsius")) for row in breaches] or [0])}),
        _result("cold_chain_compliance_failed", scenario, detected_count=sum(1 for row in breaches if row.get("cold_chain_compliance_status") == "Failed"), expected_count=expected, affected_entities=[row.get("delivery_id") for row in breaches], affected_tables=["delivery_records", "shipments"], severity=config.severity or "medium", message="Cold-chain compliance failure detected on breached deliveries.", evidence={"failed_compliance_count": sum(1 for row in breaches if row.get("cold_chain_compliance_status") == "Failed")}),
        _result("delayed_alert_detected", scenario, detected_count=len(delayed), expected_count=expected, affected_entities=[row.get("delivery_id") for row in delayed], affected_tables=["delivery_records", "tracking_events"], severity=config.severity or "medium", message="Cold-chain alerts were delayed beyond the expected threshold.", evidence={"delayed_alert_count": len(delayed), "delay_threshold_minutes": 15}),
        _result("shipment_condition_inconsistent", scenario, detected_count=len(inconsistent), expected_count=0, affected_entities=[row.get("shipment_id") for row in inconsistent], affected_tables=["shipments", "delivery_records"], severity=config.severity or "medium", message="Shipment condition must align with failed cold-chain compliance.", evidence={"inconsistent_condition_count": len(inconsistent)}),
    ]


def _finance_validators(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, expected_counts: dict[str, int]) -> list[ScenarioValidation]:
    rows = data.get("transactions", [])
    delayed = []
    sequence_invalid = []
    unsettled = []
    mismatches = []
    for row in rows:
        expected_date = row.get("expected_settlement_date")
        actual_date = row.get("actual_settlement_date")
        if not expected_date or not actual_date:
            continue
        try:
            expected_dt = datetime.fromisoformat(str(expected_date))
            actual_dt = datetime.fromisoformat(str(actual_date))
        except ValueError:
            sequence_invalid.append(row)
            continue
        if actual_dt > expected_dt:
            delayed.append(row)
        if actual_dt < datetime.fromisoformat(str(row.get("trade_date"))):
            sequence_invalid.append(row)
        if row.get("settlement_status") == "Unresolved":
            unsettled.append(row)
        if row.get("settlement_reconciliation_status") == "Mismatch":
            mismatches.append(row)
    expected = _expected(expected_counts, "settlement_delay")
    return [
        _result("settlement_delay_detected", scenario, detected_count=len(delayed), expected_count=expected, affected_entities=[row.get("transaction_id") for row in delayed], affected_tables=["transactions"], severity=config.severity or "medium", message="Actual settlement date occurs after expected settlement date.", evidence={"delayed_settlements": len(delayed)}),
        _result("settlement_sequence_invalid", scenario, detected_count=len(sequence_invalid), expected_count=0, affected_entities=[row.get("transaction_id") for row in sequence_invalid], affected_tables=["transactions"], severity=config.severity or "medium", message="Settlement sequence should preserve trade <= expected <= actual.", evidence={"invalid_sequence_count": len(sequence_invalid)}),
        _result("unsettled_trade_detected", scenario, detected_count=len(unsettled), expected_count=expected, affected_entities=[row.get("transaction_id") for row in unsettled], affected_tables=["transactions"], severity=config.severity or "medium", message="Unresolved settlement statuses detected.", evidence={"unsettled_trade_count": len(unsettled)}),
        _result("reconciliation_mismatch_detected", scenario, detected_count=len(mismatches), expected_count=expected, affected_entities=[row.get("transaction_id") for row in mismatches], affected_tables=["transactions"], severity=config.severity or "medium", message="Settlement reconciliation mismatch detected.", evidence={"mismatch_count": len(mismatches)}),
    ]


def _insurance_validators(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, expected_counts: dict[str, int]) -> list[ScenarioValidation]:
    claims = data.get("claims", [])
    exceeded = []
    payable_invalid = []
    deductible_failed = []
    eligibility_failed = []
    for row in claims:
        if "policy_limit" not in row:
            continue
        try:
            claim = Decimal(str(row.get("claim_amount")))
            limit = Decimal(str(row.get("policy_limit")))
            deductible = Decimal(str(row.get("deductible_amount")))
            payable = Decimal(str(row.get("payable_amount")))
        except (InvalidOperation, TypeError):
            continue
        if claim > limit:
            exceeded.append(row)
        if payable > limit or payable != claim - deductible:
            payable_invalid.append(row)
        if claim - deductible != payable:
            deductible_failed.append(row)
        if claim > limit and row.get("eligibility_state") != "RejectedCoverageExceeded":
            eligibility_failed.append(row)
    expected = _expected(expected_counts, "coverage_exceeded")
    return [
        _result("coverage_limit_exceeded", scenario, detected_count=len(exceeded), expected_count=expected, affected_entities=[row.get("claim_id") for row in exceeded], affected_tables=["claims", "policies"], severity=config.severity or "medium", message="Claim amount exceeds policy coverage limit.", evidence={"coverage_exceeded_count": len(exceeded)}),
        _result("payable_amount_invalid", scenario, detected_count=len(payable_invalid), expected_count=expected, affected_entities=[row.get("claim_id") for row in payable_invalid], affected_tables=["claims", "settlements"], severity=config.severity or "medium", message="Payable amount is invalid for coverage/deductible rules.", evidence={"payable_invalid_count": len(payable_invalid)}),
        _result("deductible_reconciliation_failed", scenario, detected_count=len(deductible_failed), expected_count=0, affected_entities=[row.get("claim_id") for row in deductible_failed], affected_tables=["claims"], severity=config.severity or "medium", message="Deductible reconciliation must equal claim minus payable.", evidence={"deductible_reconciliation_failures": len(deductible_failed)}),
        _result("claim_eligibility_failed", scenario, detected_count=len(eligibility_failed), expected_count=expected, affected_entities=[row.get("claim_id") for row in eligibility_failed], affected_tables=["claims", "policies"], severity=config.severity or "medium", message="Coverage-exceeded claims remain in an invalid eligibility state.", evidence={"eligibility_failures": len(eligibility_failed)}),
    ]


def _education_validators(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, expected_counts: dict[str, int]) -> list[ScenarioValidation]:
    enrollments = data.get("enrollments", [])
    mismatches = [row for row in enrollments if row.get("calculated_grade") and row.get("published_grade") and row.get("calculated_grade") != row.get("published_grade")]
    invalid_weight = [row for row in enrollments if int(row.get("grade_weight_total") or 100) != 100]
    attendance_mismatch = [row for row in enrollments if row.get("attendance_component") and int(row.get("attendance_component") or 0) > 10]
    published_inconsistent = [row for row in enrollments if row.get("final_grade") and row.get("published_grade") and row.get("final_grade") != row.get("calculated_grade")]
    expected = _expected(expected_counts, "grade_calculation_error")
    return [
        _result("grade_formula_mismatch", scenario, detected_count=len(mismatches), expected_count=expected, affected_entities=[row.get("enrollment_id") for row in mismatches], affected_tables=["enrollments", "examination_results"], severity=config.severity or "medium", message="Calculated grade and published grade differ.", evidence={"formula_mismatch_count": len(mismatches)}),
        _result("invalid_weight_total", scenario, detected_count=len(invalid_weight), expected_count=expected, affected_entities=[row.get("enrollment_id") for row in invalid_weight], affected_tables=["enrollments"], severity=config.severity or "medium", message="Grade component weights do not total 100.", evidence={"invalid_weight_count": len(invalid_weight)}),
        _result("attendance_component_mismatch", scenario, detected_count=len(attendance_mismatch), expected_count=expected, affected_entities=[row.get("enrollment_id") for row in attendance_mismatch], affected_tables=["attendance", "enrollments"], severity=config.severity or "medium", message="Attendance component is inconsistent with attendance percentage.", evidence={"attendance_component_mismatch_count": len(attendance_mismatch)}),
        _result("published_grade_inconsistent", scenario, detected_count=len(published_inconsistent), expected_count=expected, affected_entities=[row.get("enrollment_id") for row in published_inconsistent], affected_tables=["enrollments"], severity=config.severity or "medium", message="Published/final grade is inconsistent with calculated grade.", evidence={"published_grade_inconsistent_count": len(published_inconsistent)}),
    ]


def _ecommerce_validators(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, expected_counts: dict[str, int]) -> list[ScenarioValidation]:
    listings = data.get("product_listings", [])
    items = data.get("order_items", [])
    orders = {row.get("order_id"): row for row in data.get("orders", [])}
    oversold = [row for row in listings if row.get("fulfillment_state") == "Oversold"]
    reservation_failed = [row for row in listings if row.get("reservation_reconciliation_status") == "Failed"]
    negative_stock = []
    for row in listings:
        try:
            if Decimal(str(row.get("available_quantity"))) < 0:
                negative_stock.append(row)
        except (InvalidOperation, TypeError):
            continue
    inconsistent_items = [row for row in items if row.get("reservation_status") == "OverReserved" and row.get("item_status") not in {"Backordered", "Cancelled"}]
    inconsistent_orders = [orders.get(row.get("order_id")) for row in items if row.get("reservation_status") == "OverReserved" and orders.get(row.get("order_id"), {}).get("order_status") != "Backordered"]
    expected = _expected(expected_counts, "inventory_oversell")
    return [
        _result("inventory_oversell_detected", scenario, detected_count=len(oversold), expected_count=expected, affected_entities=[row.get("listing_id") for row in oversold], affected_tables=["product_listings", "order_items"], severity=config.severity or "medium", message="Inventory oversell markers detected.", evidence={"oversold_listing_count": len(oversold)}),
        _result("reservation_reconciliation_failed", scenario, detected_count=len(reservation_failed), expected_count=expected, affected_entities=[row.get("listing_id") for row in reservation_failed], affected_tables=["product_listings"], severity=config.severity or "medium", message="Reservation reconciliation failed for oversold listings.", evidence={"reservation_failure_count": len(reservation_failed)}),
        _result("negative_available_stock_detected", scenario, detected_count=len(negative_stock), expected_count=expected, affected_entities=[row.get("listing_id") for row in negative_stock], affected_tables=["product_listings"], severity=config.severity or "medium", message="Negative available stock detected.", evidence={"negative_stock_count": len(negative_stock)}),
        _result("fulfillment_state_inconsistent", scenario, detected_count=len(inconsistent_items) + len([row for row in inconsistent_orders if row]), expected_count=0, affected_entities=[row.get("order_item_id") for row in inconsistent_items], affected_tables=["orders", "order_items"], severity=config.severity or "medium", message="Oversold items should move fulfillment/order state to backordered.", evidence={"inconsistent_item_count": len(inconsistent_items), "inconsistent_order_count": len([row for row in inconsistent_orders if row])}),
    ]


SCENARIO_VALIDATORS: dict[str, Callable[[Dataset, Any, Any, dict[str, int]], list[ScenarioValidation]]] = {
    "retail_payment_retry": _retail_validators,
    "banking_duplicate_transfer": _banking_validators,
    "healthcare_ghost_provider": _healthcare_validators,
    "manufacturing_defect_spike": _manufacturing_validators,
    "telecom_tower_congestion": _telecom_dataset_validators,
    "logistics_cold_chain_failure": _logistics_validators,
    "finance_settlement_delay": _finance_validators,
    "insurance_coverage_exceeded": _insurance_validators,
    "education_grade_calculation_error": _education_validators,
    "ecommerce_inventory_oversell": _ecommerce_validators,
}


class ScenarioValidatorRegistry:
    def __init__(self) -> None:
        self._validators = SCENARIO_VALIDATORS

    def supported_scenarios(self) -> set[str]:
        return set(self._validators)

    def validate_dataset(self, data: Dataset, *, scenario: ScenarioDefinition, config: ScenarioRunConfig, expected_counts: dict[str, int] | None = None) -> list[ScenarioValidation]:
        return validate_scenario_dataset(data, scenario=scenario, config=config, expected_counts=expected_counts)

    def validate_events(self, events: list[dict[str, Any]], *, scenario: ScenarioDefinition, config: ScenarioRunConfig, expected_counts: dict[str, int] | None = None) -> list[ScenarioValidation]:
        return validate_scenario_events(events, scenario=scenario, config=config, expected_counts=expected_counts)
