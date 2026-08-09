from __future__ import annotations

import copy
import random
from datetime import datetime, timedelta
from typing import Any

from dataforge.model import Dataset, DomainSpec, FailureEvent
from dataforge.scenarios.models import ScenarioDefinition, ScenarioRunConfig

REFERENCE_SCENARIO_IDS = {
    "retail_payment_retry",
    "banking_duplicate_transfer",
    "healthcare_ghost_provider",
    "manufacturing_defect_spike",
    "telecom_tower_congestion",
    "logistics_cold_chain_failure",
    "finance_settlement_delay",
    "insurance_coverage_exceeded",
    "education_grade_calculation_error",
    "ecommerce_inventory_oversell",
}


def apply_reference_scenario_mutations(
    source: Dataset,
    *,
    scenario: ScenarioDefinition,
    config: ScenarioRunConfig,
    spec: DomainSpec,
    seed: int,
    rates: dict[str, float],
) -> tuple[Dataset, list[FailureEvent], dict[str, Any]]:
    if scenario.scenario_id not in REFERENCE_SCENARIO_IDS:
        return source, [], {}
    data = copy.deepcopy(source)
    rng = random.Random(seed + 1701)
    rate = max(rates.values() or [0.0])
    if rate <= 0:
        return data, [], _empty_result(scenario, config)
    if scenario.scenario_id == "retail_payment_retry":
        return _retail_payment_retry(data, scenario, config, spec, rng, seed, rate)
    if scenario.scenario_id == "banking_duplicate_transfer":
        return _banking_duplicate_transfer(data, scenario, config, spec, rng, seed, rate)
    if scenario.scenario_id == "healthcare_ghost_provider":
        return _healthcare_ghost_provider(data, scenario, config, spec, rng, seed, rate)
    if scenario.scenario_id == "manufacturing_defect_spike":
        return _manufacturing_defect_spike(data, scenario, config, spec, rng, seed, rate)
    if scenario.scenario_id == "telecom_tower_congestion":
        return _telecom_tower_congestion(data, scenario, config, spec, rng, seed, rate)
    if scenario.scenario_id == "logistics_cold_chain_failure":
        return _logistics_cold_chain_failure(data, scenario, config, spec, rng, seed, rate)
    if scenario.scenario_id == "finance_settlement_delay":
        return _finance_settlement_delay(data, scenario, config, spec, rng, seed, rate)
    if scenario.scenario_id == "insurance_coverage_exceeded":
        return _insurance_coverage_exceeded(data, scenario, config, spec, rng, seed, rate)
    if scenario.scenario_id == "education_grade_calculation_error":
        return _education_grade_calculation_error(data, scenario, config, spec, rng, seed, rate)
    if scenario.scenario_id == "ecommerce_inventory_oversell":
        return _ecommerce_inventory_oversell(data, scenario, config, spec, rng, seed, rate)
    return data, [], _empty_result(scenario, config)


def _target_indices(rows: list[dict[str, Any]], rng: random.Random, rate: float) -> list[int]:
    if not rows:
        return []
    count = max(1, int(len(rows) * rate))
    return sorted(rng.sample(range(len(rows)), min(count, len(rows))))


def _event(
    failure_type: str,
    table: str,
    column: str | None,
    count: int,
    *,
    seed: int,
    rate: float,
    target_locator: list[Any],
    expected_validation: str,
    severity: str,
    details: dict[str, Any] | None = None,
) -> FailureEvent:
    return FailureEvent(
        failure_type,
        table,
        column,
        count,
        {
            "requested_rate": rate,
            "eligible_row_count": max(count, len(target_locator)),
            "selected_row_count": count,
            "actual_affected_count": count,
            "target_locator": target_locator,
            "seed": seed,
            "severity": severity,
            "expected_validation": expected_validation,
            **(details or {}),
        },
    )


def _scenario_result(scenario: ScenarioDefinition, config: ScenarioRunConfig, events: list[FailureEvent], warnings: list[str] | None = None) -> dict[str, Any]:
    requested = {failure.issue_type: failure.requested_rate for failure in scenario.failure_injections}
    selected = {event.failure_type: event.details.get("selected_row_count", event.count) for event in events}
    actual = {event.failure_type: event.count for event in events}
    return {
        "requested_failure_counts": requested,
        "selected_target_counts": selected,
        "actual_mutation_counts": actual,
        "expected_validation_ids": scenario.expected_validations,
        "detected_validation_ids": [event.details.get("expected_validation") for event in events if event.details.get("expected_validation")],
        "reconciliation_by_failure": {
            event.failure_type: {
                "requested_rate": event.details.get("requested_rate"),
                "selected": event.details.get("selected_row_count", event.count),
                "actual": event.count,
                "status": "PASS" if event.count == event.details.get("selected_row_count", event.count) else "FAIL",
            }
            for event in events
        },
        "scenario_outcome": "PASS" if events and all(event.count > 0 for event in events) else "FAIL",
        "warnings": warnings or list(config.warnings),
    }


def _empty_result(scenario: ScenarioDefinition, config: ScenarioRunConfig) -> dict[str, Any]:
    return _scenario_result(scenario, config, [], warnings=["No scenario-specific mutations were applied."])


def _retail_payment_retry(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, spec: DomainSpec, rng: random.Random, seed: int, rate: float):
    rows = data.get("payments", [])
    indices = _target_indices(rows, rng, rate)
    new_rows = []
    for index in indices:
        original = rows[index]
        original["idempotency_key"] = f"idem-{original.get('sale_id')}-{original.get('customer_id')}"
        original["processor_response"] = "captured"
        retry = copy.deepcopy(original)
        retry["processor_response"] = "retry_timeout"
        retry["retry_of_payment_id"] = original.get("payment_id")
        retry["payment_timestamp"] = (datetime.fromisoformat(str(original["payment_timestamp"])) + timedelta(minutes=5)).isoformat()
        new_rows.append(retry)
    rows.extend(new_rows)
    events = [
        _event("duplicate_business_payment", "payments", "payment_id", len(indices), seed=seed, rate=rate, target_locator=[rows[i].get("payment_id") for i in indices], expected_validation="duplicate_business_payment_detected", severity=config.severity or "medium", details={"idempotency_reused": True, "optional_double_capture": "duplicate_capture" in config.variation_ids}),
        _event("duplicate_idempotency_key", "payments", "idempotency_key", len(indices), seed=seed, rate=rate, target_locator=[rows[i].get("sale_id") for i in indices], expected_validation="duplicate_idempotency_key_detected", severity=config.severity or "medium"),
    ] if indices else []
    return data, events, _scenario_result(scenario, config, events)


def _banking_duplicate_transfer(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, spec: DomainSpec, rng: random.Random, seed: int, rate: float):
    rows = data.get("transfers", [])
    indices = _target_indices(rows, rng, rate)
    new_rows = []
    for index in indices:
        original = rows[index]
        original["transfer_reference"] = f"transfer-ref-{original.get('source_account_id')}-{original.get('destination_account_id')}-{original.get('transfer_amount')}"
        original["settlement_state"] = "settled"
        original["ledger_posting_impact"] = "posted"
        duplicate = copy.deepcopy(original)
        duplicate["settlement_state"] = "duplicate_before_settlement" if "duplicate_before_settlement" in config.variation_ids else "replayed"
        duplicate["ledger_posting_impact"] = "double_posted"
        duplicate["transfer_timestamp"] = (datetime.fromisoformat(str(original["transfer_timestamp"])) + timedelta(minutes=3)).isoformat()
        new_rows.append(duplicate)
    rows.extend(new_rows)
    events = [
        _event("duplicate_transfer", "transfers", "transfer_id", len(indices), seed=seed, rate=rate, target_locator=[rows[i].get("transfer_id") for i in indices], expected_validation="duplicate_transfer_detected", severity=config.severity or "medium", details={"same_transfer_reference": True, "ledger_posting_impact": "double_posted"}),
        _event("duplicate_ledger_posting", "transfers", "ledger_posting_impact", len(indices), seed=seed, rate=rate, target_locator=[rows[i].get("transfer_id") for i in indices], expected_validation="duplicate_ledger_posting_detected", severity=config.severity or "medium"),
    ] if indices else []
    return data, events, _scenario_result(scenario, config, events)


def _healthcare_ghost_provider(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, spec: DomainSpec, rng: random.Random, seed: int, rate: float):
    rows = data.get("claims", [])
    indices = _target_indices(rows, rng, rate)
    for ordinal, index in enumerate(indices, 1):
        rows[index]["provider_id"] = f"PRV-GHOST-{seed}-{ordinal:04d}"
        rows[index]["provider_eligibility_status"] = "missing_from_master"
        rows[index]["claim_enrichment_status"] = "failed_provider_lookup"
    events = [
        _event("ghost_provider", "claims", "provider_id", len(indices), seed=seed, rate=rate, target_locator=[rows[i].get("claim_id") for i in indices], expected_validation="orphan_provider_detected", severity=config.severity or "medium", details={"provider_identifier_format": "valid_looking_missing_master"}),
    ] if indices else []
    return data, events, _scenario_result(scenario, config, events)


def _manufacturing_defect_spike(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, spec: DomainSpec, rng: random.Random, seed: int, rate: float):
    rows = data.get("quality_checks", [])
    indices = _target_indices(rows, rng, rate)
    batch_ids = []
    for index in indices:
        rows[index]["defect_count"] = max(int(rows[index].get("defect_count") or 0) + 25, 25)
        rows[index]["pass_percentage"] = "55.00"
        rows[index]["defect_spike_reason"] = (config.variation_ids or ["batch_spike"])[0]
        batch_ids.append(rows[index].get("batch_id"))
    for batch in data.get("production_batches", []):
        if batch.get("batch_id") in batch_ids:
            batch["quantity_rejected"] = max(int(batch.get("quantity_rejected") or 0) + 20, 20)
            batch["batch_status"] = "Hold"
    events = [
        _event("defect_spike", "quality_checks", "defect_count", len(indices), seed=seed, rate=rate, target_locator=[rows[i].get("quality_check_id") for i in indices], expected_validation="defect_rate_threshold_exceeded", severity=config.severity or "medium", details={"affected_batches": batch_ids}),
    ] if indices else []
    return data, events, _scenario_result(scenario, config, events)


def _telecom_tower_congestion(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, spec: DomainSpec, rng: random.Random, seed: int, rate: float):
    sessions = data.get("data_sessions", [])
    calls = data.get("call_detail_records", [])
    indices = _target_indices(sessions, rng, rate)
    tower_ids = {sessions[index].get("tower_id") for index in indices}
    for index in indices:
        sessions[index]["data_used_mb"] = max(float(sessions[index].get("data_used_mb") or 0) * 8, 2048)
        sessions[index]["session_status"] = "Failed"
        sessions[index]["congestion_marker"] = "tower_load_increase"
    call_count = 0
    for call in calls:
        if call.get("tower_id") in tower_ids and call_count < len(indices):
            call["call_status"] = "Dropped"
            call["congestion_marker"] = "dropped_call_due_to_congestion"
            call_count += 1
    for event in data.get("network_events", [])[: max(1, len(indices))]:
        event["event_type"] = "Congestion"
        event["severity"] = "High"
        event["status"] = "Active"
    events = [
        _event("tower_congestion", "data_sessions", "data_used_mb", len(indices), seed=seed, rate=rate, target_locator=[sessions[i].get("session_id") for i in indices], expected_validation="tower_congestion_detected", severity=config.severity or "medium", details={"affected_towers": sorted(tower_ids)}),
        _event("dropped_call_rate", "call_detail_records", "call_status", call_count, seed=seed, rate=rate, target_locator=list(tower_ids), expected_validation="dropped_call_rate_exceeded", severity=config.severity or "medium"),
    ] if indices else []
    return data, events, _scenario_result(scenario, config, events)


def _logistics_cold_chain_failure(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, spec: DomainSpec, rng: random.Random, seed: int, rate: float):
    deliveries = data.get("delivery_records", [])
    shipments = {row.get("shipment_id"): row for row in data.get("shipments", [])}
    tracking = data.get("tracking_events", [])
    indices = _target_indices(deliveries, rng, rate)
    affected_shipments = []
    delayed_alerts = 0
    for index in indices:
        delivery = deliveries[index]
        shipment_id = delivery.get("shipment_id")
        affected_shipments.append(shipment_id)
        delivery["temperature_celsius"] = "14.8"
        delivery["temperature_threshold_celsius"] = "8.0"
        delivery["breach_duration_minutes"] = 95
        delivery["cold_chain_alert_delay_minutes"] = 45
        delivery["shipment_condition"] = "Compromised"
        delivery["cold_chain_compliance_status"] = "Failed"
        delivery["delivery_time_minutes"] = max(int(delivery.get("delivery_time_minutes") or 0) + 360, 480)
        if shipment_id in shipments:
            shipments[shipment_id]["shipment_type"] = "Cold Chain"
            shipments[shipment_id]["shipment_status"] = "Exception"
            shipments[shipment_id]["condition_at_delivery"] = "Compromised"
        delayed_alerts += 1
    for event in tracking:
        if event.get("shipment_id") in set(affected_shipments):
            event["event_type"] = "temperature_alert_delayed"
            event["alert_delay_minutes"] = 45
    events = [
        _event("temperature_breach", "delivery_records", "temperature_celsius", len(indices), seed=seed, rate=rate, target_locator=[deliveries[i].get("delivery_id") for i in indices], expected_validation="temperature_breach_detected", severity=config.severity or "medium", details={"threshold_celsius": 8.0}),
        _event("delayed_cold_chain_alert", "tracking_events", "event_type", delayed_alerts, seed=seed, rate=rate, target_locator=affected_shipments, expected_validation="delayed_alert_detected", severity=config.severity or "medium"),
    ] if indices else []
    return data, events, _scenario_result(scenario, config, events)


def _finance_settlement_delay(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, spec: DomainSpec, rng: random.Random, seed: int, rate: float):
    rows = data.get("transactions", [])
    indices = _target_indices(rows, rng, rate)
    for index in indices:
        transaction = rows[index]
        trade_date = datetime.fromisoformat(str(transaction["transaction_timestamp"]))
        expected_settlement = trade_date + timedelta(days=2)
        actual_settlement = expected_settlement + timedelta(days=5)
        transaction["trade_date"] = trade_date.date().isoformat()
        transaction["expected_settlement_date"] = expected_settlement.date().isoformat()
        transaction["actual_settlement_date"] = actual_settlement.date().isoformat()
        transaction["asset_type"] = "equity"
        transaction["settlement_status"] = "Unresolved"
        transaction["settlement_reconciliation_status"] = "Mismatch"
        transaction["transaction_timestamp"] = actual_settlement.isoformat()
        transaction["transaction_status"] = "Pending"
    events = [
        _event("settlement_delay", "transactions", "actual_settlement_date", len(indices), seed=seed, rate=rate, target_locator=[rows[i].get("transaction_id") for i in indices], expected_validation="settlement_delay_detected", severity=config.severity or "medium", details={"expected_lag_days": 2, "actual_extra_delay_days": 5}),
    ] if indices else []
    return data, events, _scenario_result(scenario, config, events)


def _insurance_coverage_exceeded(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, spec: DomainSpec, rng: random.Random, seed: int, rate: float):
    claims = data.get("claims", [])
    policies = {row.get("policy_id"): row for row in data.get("policies", [])}
    settlements = data.get("settlements", [])
    indices = _target_indices(claims, rng, rate)
    affected_claims = []
    for index in indices:
        claim = claims[index]
        policy = policies.get(claim.get("policy_id"))
        limit = float(policy.get("coverage_amount") if policy else 10_000)
        deductible = round(max(250.0, limit * 0.02), 2)
        claim_amount = round(limit * 1.35, 2)
        payable = round(claim_amount - deductible, 2)
        claim["claim_amount"] = claim_amount
        claim["policy_limit"] = limit
        claim["deductible_amount"] = deductible
        claim["payable_amount"] = payable
        claim["eligibility_state"] = "IneligibleCoverageExceeded"
        claim["claim_status"] = "Approved"
        affected_claims.append(claim.get("claim_id"))
    for settlement in settlements:
        if settlement.get("claim_id") in affected_claims:
            claim = next((row for row in claims if row.get("claim_id") == settlement.get("claim_id")), None)
            if claim:
                settlement["settlement_amount"] = claim.get("payable_amount")
                settlement["settlement_status"] = "Approved"
    events = [
        _event("coverage_exceeded", "claims", "claim_amount", len(indices), seed=seed, rate=rate, target_locator=affected_claims, expected_validation="coverage_limit_exceeded", severity=config.severity or "medium", details={"payable_uses_claim_minus_deductible": True}),
    ] if indices else []
    return data, events, _scenario_result(scenario, config, events)


def _education_grade_calculation_error(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, spec: DomainSpec, rng: random.Random, seed: int, rate: float):
    enrollments = data.get("enrollments", [])
    indices = _target_indices(enrollments, rng, rate)
    enrollment_ids = []
    for index in indices:
        enrollment = enrollments[index]
        enrollment_id = enrollment.get("enrollment_id")
        student_id = enrollment.get("student_id")
        enrollment_ids.append(enrollment_id)
        enrollment["attendance_component"] = 15
        enrollment["assignment_component"] = 40
        enrollment["exam_component"] = 55
        enrollment["grade_weight_total"] = 110
        enrollment["calculated_grade"] = "B"
        enrollment["published_grade"] = "A"
        enrollment["final_grade"] = "A"
        enrollment["grade_calculation_status"] = "FormulaMismatch"
        for attendance in data.get("attendance", []):
            if attendance.get("enrollment_id") == enrollment_id:
                attendance["attendance_percentage"] = 52
                attendance["attendance_component"] = 15
        for submission in data.get("assignment_submissions", []):
            if submission.get("student_id") == student_id:
                submission["marks_obtained"] = 40
        for result in data.get("examination_results", []):
            if result.get("student_id") == student_id:
                result["marks_obtained"] = -5
                result["grade"] = "A"
                result["grade_calculation_status"] = "FormulaMismatch"
                break
    events = [
        _event("grade_calculation_error", "enrollments", "final_grade", len(indices), seed=seed, rate=rate, target_locator=enrollment_ids, expected_validation="grade_formula_mismatch", severity=config.severity or "medium", details={"invalid_weight_total": 110}),
    ] if indices else []
    return data, events, _scenario_result(scenario, config, events)


def _ecommerce_inventory_oversell(data: Dataset, scenario: ScenarioDefinition, config: ScenarioRunConfig, spec: DomainSpec, rng: random.Random, seed: int, rate: float):
    listings = data.get("product_listings", [])
    order_items = data.get("order_items", [])
    orders = {row.get("order_id"): row for row in data.get("orders", [])}
    indices = _target_indices(listings, rng, rate)
    affected_listings = []
    for index in indices:
        listing = listings[index]
        listing_id = listing.get("listing_id")
        affected_listings.append(listing_id)
        listing["available_quantity_before"] = max(int(listing.get("available_quantity") or 0), 1)
        listing["reserved_quantity"] = listing["available_quantity_before"] + 3
        listing["concurrent_order_count"] = 3
        listing["available_quantity"] = -3
        listing["reservation_reconciliation_status"] = "Failed"
        listing["fulfillment_state"] = "Oversold"
        touched = 0
        for item in order_items:
            if item.get("listing_id") != listing_id:
                continue
            item["quantity"] = max(int(item.get("quantity") or 1), listing["available_quantity_before"] + 1)
            item["reservation_status"] = "OverReserved"
            item["inventory_deduction_status"] = "NegativeStock"
            item["item_status"] = "Backordered"
            order = orders.get(item.get("order_id"))
            if order:
                order["order_status"] = "Backordered"
            touched += 1
            if touched >= 2:
                break
    events = [
        _event("inventory_oversell", "product_listings", "available_quantity", len(indices), seed=seed, rate=rate, target_locator=affected_listings, expected_validation="inventory_oversell_detected", severity=config.severity or "medium", details={"negative_available_stock": True}),
    ] if indices else []
    return data, events, _scenario_result(scenario, config, events)
