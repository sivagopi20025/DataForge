from __future__ import annotations

DATE_COLUMNS = {
    "customers": "created_at",
    "accounts": "opened_date",
    "transactions": "transaction_timestamp",
    "cards": "issued_date",
    "loans": "start_date",
    "payments": "payment_date",
    "trades": "trade_timestamp",
    "market_data": "quote_timestamp",
    "positions": "position_date",
    "risk_events": "event_timestamp",
}

NUMERIC_COLUMNS = {
    "accounts": "balance",
    "transactions": "transaction_amount",
    "loans": "loan_amount",
    "payments": "payment_amount",
    "trades": "notional_amount",
    "market_data": "price",
    "positions": "market_value",
    "risk_events": "exposure_amount",
}

TYPE_MISMATCH_COLUMNS = {
    "customers": "first_name",
    "accounts": "account_status",
    "transactions": "transaction_status",
    "cards": "card_status",
    "loans": "interest_rate",
    "payments": "payment_status",
    "trades": "trade_status",
    "market_data": "market_status",
    "positions": "position_status",
    "risk_events": "risk_status",
}
