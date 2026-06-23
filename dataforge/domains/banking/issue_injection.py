from __future__ import annotations

DATE_COLUMNS = {
    "customers": "created_at",
    "deposit_accounts": "opened_date",
    "payments": "payment_timestamp",
    "transfers": "transfer_timestamp",
    "treasury_positions": "position_date",
    "treasury_transactions": "transaction_date",
}

NUMERIC_COLUMNS = {
    "deposit_accounts": "balance",
    "payments": "amount",
    "transfers": "transfer_amount",
    "treasury_positions": "cash_position",
    "treasury_transactions": "transaction_amount",
}

TYPE_MISMATCH_COLUMNS = {
    "customers": "risk_rating",
    "branches": "status",
    "deposit_accounts": "account_status",
    "payments": "payment_status",
    "transfers": "transfer_status",
    "treasury_positions": "liquidity_ratio",
    "treasury_transactions": "transaction_type",
}
