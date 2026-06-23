from __future__ import annotations

DATE_COLUMNS = {
    "customers": "created_at",
    "accounts": "opened_date",
    "transactions": "transaction_timestamp",
    "cards": "issued_date",
    "loans": "start_date",
    "payments": "payment_date",
}

NUMERIC_COLUMNS = {
    "accounts": "balance",
    "transactions": "transaction_amount",
    "loans": "loan_amount",
    "payments": "payment_amount",
}

TYPE_MISMATCH_COLUMNS = {
    "customers": "first_name",
    "accounts": "account_status",
    "transactions": "transaction_status",
    "cards": "card_status",
    "loans": "interest_rate",
    "payments": "payment_status",
}
