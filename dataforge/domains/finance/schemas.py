from __future__ import annotations

from ...model import DomainSpec, EventDefinition, ForeignKey, TableSchema, with_enterprise_columns
from .issue_injection import DATE_COLUMNS, NUMERIC_COLUMNS, TYPE_MISMATCH_COLUMNS
from .validations import BUSINESS_RULES


BASE_SCHEMAS: dict[str, TableSchema] = {
    "customers": TableSchema("customer_id", ("customer_id", "first_name", "last_name", "dob", "gender", "email", "phone", "city", "state", "country", "customer_segment", "created_at")),
    "accounts": TableSchema("account_id", ("account_id", "customer_id", "account_type", "account_status", "balance", "opened_date"), (ForeignKey("customer_id", "customers", "customer_id"),)),
    "transactions": TableSchema("transaction_id", ("transaction_id", "account_id", "transaction_type", "transaction_amount", "transaction_timestamp", "merchant_name", "transaction_status", "fraud_scenario", "is_fraud_scenario"), (ForeignKey("account_id", "accounts", "account_id"),)),
    "cards": TableSchema("card_id", ("card_id", "customer_id", "account_id", "card_type", "card_network", "card_status", "issued_date"), (ForeignKey("customer_id", "customers", "customer_id"), ForeignKey("account_id", "accounts", "account_id"))),
    "loans": TableSchema("loan_id", ("loan_id", "customer_id", "loan_type", "loan_amount", "interest_rate", "loan_status", "start_date"), (ForeignKey("customer_id", "customers", "customer_id"),)),
    "payments": TableSchema("payment_id", ("payment_id", "loan_id", "customer_id", "payment_amount", "payment_date", "payment_status"), (ForeignKey("loan_id", "loans", "loan_id"), ForeignKey("customer_id", "customers", "customer_id"))),
    "risk_events": TableSchema("risk_event_id", ("risk_event_id", "account_id", "event_timestamp", "risk_score", "risk_category", "risk_status", "risk_reason", "exposure_amount"), (ForeignKey("account_id", "accounts", "account_id"),)),
    "trades": TableSchema("trade_id", ("trade_id", "account_id", "instrument_symbol", "trade_side", "quantity", "price", "notional_amount", "trade_timestamp", "trade_status", "rejection_reason", "risk_event_id"), (ForeignKey("account_id", "accounts", "account_id"), ForeignKey("risk_event_id", "risk_events", "risk_event_id", nullable=True))),
    "market_data": TableSchema("market_data_id", ("market_data_id", "instrument_symbol", "quote_timestamp", "price", "bid_price", "ask_price", "market_status", "market_event_reason", "risk_event_id"), (ForeignKey("risk_event_id", "risk_events", "risk_event_id", nullable=True),)),
    "positions": TableSchema("position_id", ("position_id", "account_id", "instrument_symbol", "quantity", "average_cost", "market_value", "position_date", "position_status", "position_reason", "risk_event_id"), (ForeignKey("account_id", "accounts", "account_id"), ForeignKey("risk_event_id", "risk_events", "risk_event_id", nullable=True))),
}

FACT_TABLES = {"transactions", "payments", "risk_events", "trades", "market_data", "positions"}
DIMENSION_TABLES = {"customers", "accounts", "cards", "loans"}


FINANCE_SPEC = DomainSpec(
    name="finance",
    source_system="DATAFORGE_FINANCE",
    schemas=with_enterprise_columns(BASE_SCHEMAS, FACT_TABLES, DIMENSION_TABLES),
    fact_tables=FACT_TABLES,
    dimension_tables=DIMENSION_TABLES,
    timestamp_sources={
        "transactions": "transaction_timestamp",
        "payments": "payment_date",
        "trades": "trade_timestamp",
        "market_data": "quote_timestamp",
        "positions": "position_date",
        "risk_events": "event_timestamp",
    },
    date_columns=DATE_COLUMNS,
    numeric_columns=NUMERIC_COLUMNS,
    type_mismatch_columns=TYPE_MISMATCH_COLUMNS,
    event_definitions=(
        EventDefinition("transaction_event", "transactions", "TRANSACTION_COMPLETED", "transaction_id", "transaction_timestamp"),
        EventDefinition("card_event", "cards", "CARD_UPDATED", "card_id", "updated_ts"),
        EventDefinition("payment_event", "payments", "PAYMENT_COMPLETED", "payment_id", "payment_date"),
        EventDefinition("fraud_event", "transactions", "FRAUD_SIGNAL", "transaction_id", "transaction_timestamp", sample_every=25),
        EventDefinition("trade_event", "trades", "TRADE_UPDATED", "trade_id", "trade_timestamp"),
        EventDefinition("market_data_event", "market_data", "MARKET_DATA_UPDATED", "market_data_id", "quote_timestamp"),
        EventDefinition("risk_event", "risk_events", "RISK_EVENT_UPDATED", "risk_event_id", "event_timestamp"),
    ),
    cdc_tables=("accounts", "transactions", "cards", "loans", "payments", "trades", "market_data", "positions", "risk_events"),
    business_rules=BUSINESS_RULES,
)
