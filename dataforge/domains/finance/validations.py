from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from .constants import ACCOUNT_STATUSES, ACCOUNT_TYPES, CARD_STATUSES, CARD_TYPES, LOAN_STATUSES, PAYMENT_STATUSES, TRANSACTION_STATUSES, TRANSACTION_TYPES


def account_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    invalid_status = sum(1 for row in data.get("accounts", []) if row.get("account_status") not in ACCOUNT_STATUSES)
    invalid_type = sum(1 for row in data.get("accounts", []) if row.get("account_type") not in ACCOUNT_TYPES)
    negative_savings = 0
    for account in data.get("accounts", []):
        if account.get("account_type") != "Savings":
            continue
        try:
            negative_savings += Decimal(str(account["balance"])) < 0
        except InvalidOperation:
            negative_savings += 1
    return [
        {"check": "account_status_valid", "table": "accounts", "failures": invalid_status},
        {"check": "account_type_valid", "table": "accounts", "failures": invalid_type},
        {"check": "savings_balance_non_negative", "table": "accounts", "failures": negative_savings},
    ]


def transaction_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    accounts = {row["account_id"]: row for row in data.get("accounts", [])}
    invalid_status = sum(1 for row in data.get("transactions", []) if row.get("transaction_status") not in TRANSACTION_STATUSES)
    invalid_type = sum(1 for row in data.get("transactions", []) if row.get("transaction_type") not in TRANSACTION_TYPES)
    closed_or_frozen_processed = 0
    negative_amounts = 0
    for transaction in data.get("transactions", []):
        account = accounts.get(transaction.get("account_id"))
        if account and account.get("account_status") in {"Closed", "Frozen"}:
            closed_or_frozen_processed += transaction.get("transaction_status") == "Success"
        try:
            negative_amounts += Decimal(str(transaction["transaction_amount"])) < 0
        except InvalidOperation:
            negative_amounts += 1
    return [
        {"check": "transaction_status_valid", "table": "transactions", "failures": invalid_status},
        {"check": "transaction_type_valid", "table": "transactions", "failures": invalid_type},
        {"check": "closed_or_frozen_accounts_cannot_process_transactions", "table": "transactions", "failures": closed_or_frozen_processed},
        {"check": "transaction_amount_non_negative", "table": "transactions", "failures": negative_amounts},
    ]


def card_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    invalid_status = sum(1 for row in data.get("cards", []) if row.get("card_status") not in CARD_STATUSES)
    invalid_type = sum(1 for row in data.get("cards", []) if row.get("card_type") not in CARD_TYPES)
    return [
        {"check": "card_status_valid", "table": "cards", "failures": invalid_status},
        {"check": "card_type_valid", "table": "cards", "failures": invalid_type},
    ]


def loan_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    invalid_status = sum(1 for row in data.get("loans", []) if row.get("loan_status") not in LOAN_STATUSES)
    invalid_interest = 0
    negative_loans = 0
    for loan in data.get("loans", []):
        try:
            interest = Decimal(str(loan["interest_rate"]))
            amount = Decimal(str(loan["loan_amount"]))
            invalid_interest += interest < 0 or interest > Decimal("35")
            negative_loans += amount < 0
        except InvalidOperation:
            invalid_interest += 1
    return [
        {"check": "loan_status_valid", "table": "loans", "failures": invalid_status},
        {"check": "interest_rate_valid", "table": "loans", "failures": invalid_interest},
        {"check": "loan_amount_non_negative", "table": "loans", "failures": negative_loans},
    ]


def loan_payment_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    loans = {row["loan_id"]: row for row in data.get("loans", [])}
    invalid_status = sum(1 for row in data.get("payments", []) if row.get("payment_status") not in PAYMENT_STATUSES)
    overpayments = 0
    negative_payments = 0
    for payment in data.get("payments", []):
        loan = loans.get(payment.get("loan_id"))
        try:
            payment_amount = Decimal(str(payment["payment_amount"]))
            negative_payments += payment_amount < 0
            if loan:
                overpayments += payment_amount > Decimal(str(loan["loan_amount"]))
        except InvalidOperation:
            negative_payments += 1
    return [
        {"check": "payment_status_valid", "table": "payments", "failures": invalid_status},
        {"check": "payment_amount_non_negative", "table": "payments", "failures": negative_payments},
        {"check": "payment_amount_cannot_exceed_loan_amount", "table": "payments", "failures": overpayments},
    ]


BUSINESS_RULES = (
    account_validation,
    transaction_validation,
    card_validation,
    loan_validation,
    loan_payment_validation,
)
