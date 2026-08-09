from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .constants import CLAIM_STATUSES, CPT_CODES, ICD10_CODES, PAYMENT_STATUSES


def patient_age_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    today = date(2026, 6, 22)
    failures = 0
    for patient in data.get("patients", []):
        try:
            dob = date.fromisoformat(str(patient["dob"]))
        except ValueError:
            failures += 1
            continue
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        failures += dob >= today or age < 0 or age > 100
    return [{"check": "patient_dob_in_past_age_0_to_100", "table": "patients", "failures": failures}]


def payment_amount_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    claims = {row["claim_id"]: row for row in data.get("claims", [])}
    failures = 0
    for payment in data.get("payments", []):
        claim = claims.get(payment.get("claim_id"))
        if not claim:
            continue
        try:
            failures += Decimal(str(payment["payment_amount"])) > Decimal(str(claim["claim_amount"]))
        except InvalidOperation:
            failures += 1
    return [{"check": "payment_amount_cannot_exceed_claim_amount", "table": "payments", "failures": failures}]


def icd_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    allowed = {code for code, _ in ICD10_CODES}
    failures = sum(1 for row in data.get("diagnoses", []) if row.get("icd10_code") not in allowed)
    return [{"check": "icd10_code_valid", "table": "diagnoses", "failures": failures}]


def cpt_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    allowed = {code for code, _ in CPT_CODES}
    failures = sum(1 for row in data.get("procedures", []) if row.get("cpt_code") not in allowed)
    return [{"check": "cpt_code_valid", "table": "procedures", "failures": failures}]


def claim_lifecycle_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    payments_by_claim: dict[Any, list[dict[str, Any]]] = {}
    for payment in data.get("payments", []):
        payments_by_claim.setdefault(payment.get("claim_id"), []).append(payment)
    invalid_claim_status = sum(1 for row in data.get("claims", []) if row.get("claim_status") not in CLAIM_STATUSES)
    invalid_payment_status = sum(1 for row in data.get("payments", []) if row.get("payment_status") not in PAYMENT_STATUSES)
    paid_without_payment = 0
    for claim in data.get("claims", []):
        if claim.get("claim_status") == "Paid":
            related = payments_by_claim.get(claim.get("claim_id"), [])
            paid_without_payment += not any(payment.get("payment_status") in {"Paid", "Partial"} for payment in related)
    return [
        {"check": "claim_status_valid", "table": "claims", "failures": invalid_claim_status},
        {"check": "payment_status_valid", "table": "payments", "failures": invalid_payment_status},
        {"check": "paid_claim_has_payment", "table": "claims", "failures": paid_without_payment},
    ]


def visit_temporal_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    visits = {row["visit_id"]: row for row in data.get("visits", [])}
    failures = 0
    for claim in data.get("claims", []):
        visit = visits.get(claim.get("visit_id"))
        if not visit:
            continue
        try:
            failures += datetime.fromisoformat(str(claim["submitted_date"])) < datetime.fromisoformat(str(visit["visit_date"]))
        except ValueError:
            failures += 1
    return [{"check": "claim_not_submitted_before_visit", "table": "claims", "failures": failures}]


def prior_authorization_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    allowed_statuses = {"Approved", "Denied", "Pending"}
    procedure_codes = {row["procedure_id"]: row.get("cpt_code") for row in data.get("procedures", []) if "procedure_id" in row}
    failures = 0
    for row in data.get("prior_authorizations", []):
        try:
            status = row.get("authorization_status")
            failures += status not in allowed_statuses
            failures += Decimal(str(row["approved_amount"])) < 0
            if row.get("procedure_id") in procedure_codes:
                failures += row.get("procedure_code") != procedure_codes[row["procedure_id"]]
            if status == "Approved":
                approved = datetime.fromisoformat(str(row["approved_at"]))
                requested = datetime.fromisoformat(str(row["requested_at"]))
                failures += approved <= requested
                failures += Decimal(str(row["approved_amount"])) <= 0
                failures += row.get("expiration_date") == "not_applicable"
                failures += row.get("denial_reason") != "not_applicable"
            if status == "Denied":
                failures += row.get("denial_reason") == "not_applicable"
                failures += row.get("approved_amount") not in {"0.00", "0"}
            if status == "Pending":
                failures += row.get("approved_at") != "not_applicable"
                failures += row.get("denial_reason") != "not_applicable"
        except (InvalidOperation, KeyError, ValueError, TypeError):
            failures += 1
    return [{"check": "prior_authorization_status_and_dates_valid", "table": "prior_authorizations", "failures": failures}]


BUSINESS_RULES = (
    patient_age_validation,
    payment_amount_validation,
    icd_validation,
    cpt_validation,
    claim_lifecycle_validation,
    visit_temporal_validation,
    prior_authorization_validation,
)
