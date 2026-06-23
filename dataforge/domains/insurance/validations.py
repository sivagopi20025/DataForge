from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .constants import AGENT_STATUSES, CLAIM_STATUSES, POLICY_STATUSES, PREMIUM_STATUSES, SETTLEMENT_STATUSES


def agent_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = sum(1 for row in data.get("agents", []) if row.get("agent_status") not in AGENT_STATUSES)
    return [{"check": "agent_status_valid", "table": "agents", "failures": failures}]


def policy_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    invalid_status = 0
    invalid_dates = 0
    negative_coverage = 0
    negative_premium = 0
    for policy in data.get("policies", []):
        invalid_status += policy.get("policy_status") not in POLICY_STATUSES
        try:
            invalid_dates += datetime.fromisoformat(str(policy["policy_end_date"])) < datetime.fromisoformat(str(policy["policy_start_date"]))
        except ValueError:
            invalid_dates += 1
        try:
            negative_coverage += Decimal(str(policy["coverage_amount"])) < 0
            negative_premium += Decimal(str(policy["premium_amount"])) < 0
        except InvalidOperation:
            negative_coverage += 1
    return [
        {"check": "policy_status_valid", "table": "policies", "failures": invalid_status},
        {"check": "policy_end_not_before_start", "table": "policies", "failures": invalid_dates},
        {"check": "coverage_amount_non_negative", "table": "policies", "failures": negative_coverage},
        {"check": "policy_premium_non_negative", "table": "policies", "failures": negative_premium},
    ]


def premium_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    policies = {row["policy_id"]: row for row in data.get("policies", [])}
    invalid_status = 0
    cancelled_policy_premiums = 0
    negative_premiums = 0
    for premium in data.get("premiums", []):
        invalid_status += premium.get("premium_status") not in PREMIUM_STATUSES
        policy = policies.get(premium.get("policy_id"))
        if policy:
            cancelled_policy_premiums += policy.get("policy_status") == "Cancelled"
        try:
            negative_premiums += Decimal(str(premium["premium_amount"])) < 0
        except InvalidOperation:
            negative_premiums += 1
    return [
        {"check": "premium_status_valid", "table": "premiums", "failures": invalid_status},
        {"check": "cancelled_policies_cannot_generate_premiums", "table": "premiums", "failures": cancelled_policy_premiums},
        {"check": "premium_amount_non_negative", "table": "premiums", "failures": negative_premiums},
    ]


def claim_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    policies = {row["policy_id"]: row for row in data.get("policies", [])}
    invalid_status = 0
    over_coverage = 0
    expired_or_cancelled_active_claims = 0
    negative_claims = 0
    for claim in data.get("claims", []):
        invalid_status += claim.get("claim_status") not in CLAIM_STATUSES
        policy = policies.get(claim.get("policy_id"))
        try:
            claim_amount = Decimal(str(claim["claim_amount"]))
            negative_claims += claim_amount < 0
            if policy:
                over_coverage += claim_amount > Decimal(str(policy["coverage_amount"]))
                expired_or_cancelled_active_claims += policy.get("policy_status") in {"Expired", "Cancelled"} and claim.get("claim_status") in {"Submitted", "Under Review", "Approved"}
        except InvalidOperation:
            negative_claims += 1
    return [
        {"check": "claim_status_valid", "table": "claims", "failures": invalid_status},
        {"check": "claim_amount_cannot_exceed_coverage", "table": "claims", "failures": over_coverage},
        {"check": "expired_or_cancelled_policies_cannot_accept_active_claims", "table": "claims", "failures": expired_or_cancelled_active_claims},
        {"check": "claim_amount_non_negative", "table": "claims", "failures": negative_claims},
    ]


def settlement_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    claims = {row["claim_id"]: row for row in data.get("claims", [])}
    invalid_status = 0
    over_claim = 0
    negative_settlements = 0
    for settlement in data.get("settlements", []):
        invalid_status += settlement.get("settlement_status") not in SETTLEMENT_STATUSES
        claim = claims.get(settlement.get("claim_id"))
        try:
            settlement_amount = Decimal(str(settlement["settlement_amount"]))
            negative_settlements += settlement_amount < 0
            if claim:
                over_claim += settlement_amount > Decimal(str(claim["claim_amount"]))
        except InvalidOperation:
            negative_settlements += 1
    return [
        {"check": "settlement_status_valid", "table": "settlements", "failures": invalid_status},
        {"check": "settlement_amount_cannot_exceed_claim_amount", "table": "settlements", "failures": over_claim},
        {"check": "settlement_amount_non_negative", "table": "settlements", "failures": negative_settlements},
    ]


BUSINESS_RULES = (
    agent_validation,
    policy_validation,
    premium_validation,
    claim_validation,
    settlement_validation,
)
