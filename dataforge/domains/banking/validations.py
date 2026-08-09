from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .constants import ACCOUNT_STATUSES, BRANCH_STATUSES, CARD_AUTHORIZATION_STATUSES, CARD_DECLINE_REASONS, CARD_RESPONSE_CODES, CURRENCIES, PAYMENT_STATUSES, RECONCILIATION_SCENARIOS, TRANSFER_STATUSES, TREASURY_TRANSACTION_TYPES


def branch_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = sum(1 for row in data.get("branches", []) if row.get("status") not in BRANCH_STATUSES)
    return [{"check": "branch_status_valid", "table": "branches", "failures": failures}]


def account_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    invalid_status = 0
    invalid_currency = 0
    invalid_balance = 0
    for account in data.get("deposit_accounts", []):
        invalid_status += account.get("account_status") not in ACCOUNT_STATUSES
        invalid_currency += account.get("currency") not in CURRENCIES
        try:
            Decimal(str(account["balance"]))
        except InvalidOperation:
            invalid_balance += 1
    return [
        {"check": "account_status_valid", "table": "deposit_accounts", "failures": invalid_status},
        {"check": "account_currency_valid", "table": "deposit_accounts", "failures": invalid_currency},
        {"check": "account_balance_numeric", "table": "deposit_accounts", "failures": invalid_balance},
    ]


def payment_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    accounts = {row["account_id"]: row for row in data.get("deposit_accounts", [])}
    invalid_status = 0
    invalid_currency = 0
    negative_amounts = 0
    closed_account_payments = 0
    for payment in data.get("payments", []):
        invalid_status += payment.get("payment_status") not in PAYMENT_STATUSES
        invalid_currency += payment.get("currency") not in CURRENCIES
        account = accounts.get(payment.get("account_id"))
        if account:
            closed_account_payments += account.get("account_status") == "Closed" and payment.get("payment_status") == "Completed"
            invalid_currency += payment.get("currency") != account.get("currency")
        try:
            negative_amounts += Decimal(str(payment["amount"])) < 0
        except InvalidOperation:
            negative_amounts += 1
    return [
        {"check": "payment_status_valid", "table": "payments", "failures": invalid_status},
        {"check": "payment_currency_valid", "table": "payments", "failures": invalid_currency},
        {"check": "payment_amount_non_negative", "table": "payments", "failures": negative_amounts},
        {"check": "closed_accounts_cannot_process_payments", "table": "payments", "failures": closed_account_payments},
    ]


def transfer_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    accounts = {row["account_id"]: row for row in data.get("deposit_accounts", [])}
    invalid_status = 0
    invalid_currency = 0
    non_positive_amounts = 0
    frozen_account_transfers = 0
    currency_mismatches = 0
    for transfer in data.get("transfers", []):
        invalid_status += transfer.get("transfer_status") not in TRANSFER_STATUSES
        invalid_currency += transfer.get("currency") not in CURRENCIES
        source = accounts.get(transfer.get("source_account_id"))
        destination = accounts.get(transfer.get("destination_account_id"))
        try:
            non_positive_amounts += Decimal(str(transfer["transfer_amount"])) <= 0
        except InvalidOperation:
            non_positive_amounts += 1
        if source:
            frozen_account_transfers += source.get("account_status") == "Frozen" and transfer.get("transfer_status") in {"Processing", "Completed"}
            currency_mismatches += transfer.get("currency") != source.get("currency")
        if destination:
            currency_mismatches += transfer.get("currency") != destination.get("currency")
    return [
        {"check": "transfer_status_valid", "table": "transfers", "failures": invalid_status},
        {"check": "transfer_currency_valid", "table": "transfers", "failures": invalid_currency},
        {"check": "transfer_amount_positive", "table": "transfers", "failures": non_positive_amounts},
        {"check": "frozen_accounts_cannot_process_transfers", "table": "transfers", "failures": frozen_account_transfers},
        {"check": "transfer_currency_matches_accounts", "table": "transfers", "failures": currency_mismatches},
    ]


def treasury_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    negative_positions = 0
    invalid_currency = 0
    invalid_liquidity = 0
    invalid_txn_type = sum(1 for row in data.get("treasury_transactions", []) if row.get("transaction_type") not in TREASURY_TRANSACTION_TYPES)
    negative_txns = 0
    for position in data.get("treasury_positions", []):
        invalid_currency += position.get("currency") not in CURRENCIES
        try:
            negative_positions += Decimal(str(position["cash_position"])) < 0 or Decimal(str(position["market_value"])) < 0
            ratio = Decimal(str(position["liquidity_ratio"]))
            invalid_liquidity += ratio < 0 or ratio > 1
        except InvalidOperation:
            negative_positions += 1
    for txn in data.get("treasury_transactions", []):
        try:
            negative_txns += Decimal(str(txn["transaction_amount"])) < 0
        except InvalidOperation:
            negative_txns += 1
    return [
        {"check": "treasury_position_non_negative", "table": "treasury_positions", "failures": negative_positions},
        {"check": "treasury_currency_valid", "table": "treasury_positions", "failures": invalid_currency},
        {"check": "liquidity_ratio_between_zero_and_one", "table": "treasury_positions", "failures": invalid_liquidity},
        {"check": "treasury_transaction_type_valid", "table": "treasury_transactions", "failures": invalid_txn_type},
        {"check": "treasury_transaction_amount_non_negative", "table": "treasury_transactions", "failures": negative_txns},
    ]


def card_authorization_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    accounts = {row["account_id"]: row for row in data.get("deposit_accounts", [])}
    invalid_status = 0
    invalid_currency = 0
    invalid_response = 0
    invalid_reason = 0
    invalid_amount = 0
    invalid_lifecycle = 0
    for authorization in data.get("card_authorizations", []):
        status = authorization.get("authorization_status")
        invalid_status += status not in CARD_AUTHORIZATION_STATUSES
        invalid_response += authorization.get("response_code") not in CARD_RESPONSE_CODES
        invalid_reason += authorization.get("reason_code") not in CARD_DECLINE_REASONS
        account = accounts.get(authorization.get("account_id"))
        if account:
            invalid_currency += authorization.get("currency") != account.get("currency")
        else:
            invalid_currency += authorization.get("currency") not in CURRENCIES
        try:
            amount = Decimal(str(authorization["authorization_amount"]))
            invalid_amount += amount <= 0
            authorized_at = datetime.fromisoformat(str(authorization["authorization_timestamp"]))
            expires_at = datetime.fromisoformat(str(authorization["expires_at"]))
            invalid_lifecycle += expires_at <= authorized_at
            if status == "Captured":
                captured_at = datetime.fromisoformat(str(authorization["captured_at"]))
                invalid_lifecycle += captured_at < authorized_at or captured_at > expires_at
                invalid_lifecycle += authorization.get("capture_reference") == "not_applicable"
                invalid_lifecycle += authorization.get("reason_code") != "not_applicable"
            elif status == "Declined":
                invalid_lifecycle += authorization.get("captured_at") != "not_applicable"
                invalid_lifecycle += authorization.get("capture_reference") != "not_applicable"
                invalid_lifecycle += authorization.get("reason_code") == "not_applicable"
            else:
                invalid_lifecycle += authorization.get("captured_at") != "not_applicable"
                invalid_lifecycle += authorization.get("capture_reference") != "not_applicable"
                invalid_lifecycle += authorization.get("reason_code") != "not_applicable"
        except (InvalidOperation, KeyError, ValueError, TypeError):
            invalid_amount += 1
    return [
        {"check": "card_authorization_status_valid", "table": "card_authorizations", "failures": invalid_status},
        {"check": "card_authorization_currency_matches_account", "table": "card_authorizations", "failures": invalid_currency},
        {"check": "card_authorization_response_code_valid", "table": "card_authorizations", "failures": invalid_response},
        {"check": "card_authorization_reason_code_valid", "table": "card_authorizations", "failures": invalid_reason},
        {"check": "card_authorization_amount_positive", "table": "card_authorizations", "failures": invalid_amount},
        {"check": "card_authorization_lifecycle_valid", "table": "card_authorizations", "failures": invalid_lifecycle},
    ]


def reconciliation_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    invalid_tags = sum(
        1 for row in data.get("payments", []) + data.get("transfers", [])
        if row.get("reconciliation_scenario") not in ("", None, "none") and row.get("reconciliation_scenario") not in RECONCILIATION_SCENARIOS
    )
    duplicate_completed_refs = 0
    seen: set[tuple[str, Any]] = set()
    for payment in data.get("payments", []):
        if payment.get("payment_status") != "Completed":
            continue
        key = ("payment", payment.get("payment_id"))
        duplicate_completed_refs += key in seen
        seen.add(key)
    for transfer in data.get("transfers", []):
        if transfer.get("transfer_status") != "Completed":
            continue
        key = ("transfer", transfer.get("transfer_id"))
        duplicate_completed_refs += key in seen
        seen.add(key)
    return [
        {"check": "reconciliation_scenario_valid", "table": "payments_transfers", "failures": invalid_tags},
        {"check": "completed_reconciliation_reference_unique", "table": "payments_transfers", "failures": duplicate_completed_refs},
    ]


BUSINESS_RULES = (
    branch_validation,
    account_validation,
    payment_validation,
    transfer_validation,
    card_authorization_validation,
    treasury_validation,
    reconciliation_validation,
)
