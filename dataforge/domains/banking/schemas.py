from __future__ import annotations

from ...model import DomainSpec, EventDefinition, ForeignKey, TableSchema, with_enterprise_columns
from .issue_injection import DATE_COLUMNS, NUMERIC_COLUMNS, TYPE_MISMATCH_COLUMNS
from .validations import BUSINESS_RULES


BASE_SCHEMAS: dict[str, TableSchema] = {
    "customers": TableSchema("customer_id", ("customer_id", "customer_type", "customer_name", "country", "state", "city", "risk_rating", "created_at")),
    "branches": TableSchema("branch_id", ("branch_id", "branch_name", "branch_code", "country", "state", "city", "region", "status")),
    "deposit_accounts": TableSchema("account_id", ("account_id", "customer_id", "branch_id", "account_type", "currency", "balance", "account_status", "opened_date"), (ForeignKey("customer_id", "customers", "customer_id"), ForeignKey("branch_id", "branches", "branch_id"))),
    "payments": TableSchema("payment_id", ("payment_id", "account_id", "payment_type", "amount", "currency", "payment_status", "payment_timestamp", "fraud_scenario", "is_fraud_scenario", "reconciliation_scenario", "is_reconciliation_scenario"), (ForeignKey("account_id", "deposit_accounts", "account_id"),)),
    "transfers": TableSchema("transfer_id", ("transfer_id", "source_account_id", "destination_account_id", "transfer_amount", "currency", "transfer_status", "transfer_timestamp", "reconciliation_scenario", "is_reconciliation_scenario"), (ForeignKey("source_account_id", "deposit_accounts", "account_id"), ForeignKey("destination_account_id", "deposit_accounts", "account_id"))),
    "treasury_positions": TableSchema("position_id", ("position_id", "branch_id", "position_date", "currency", "cash_position", "liquidity_ratio", "market_value"), (ForeignKey("branch_id", "branches", "branch_id"),)),
    "treasury_transactions": TableSchema("treasury_txn_id", ("treasury_txn_id", "position_id", "transaction_type", "transaction_amount", "transaction_date"), (ForeignKey("position_id", "treasury_positions", "position_id"),)),
}

FACT_TABLES = {"payments", "transfers", "treasury_positions", "treasury_transactions"}
DIMENSION_TABLES = {"customers", "branches", "deposit_accounts"}


BANKING_SPEC = DomainSpec(
    name="banking",
    source_system="DATAFORGE_BANKING",
    schemas=with_enterprise_columns(BASE_SCHEMAS, FACT_TABLES, DIMENSION_TABLES),
    fact_tables=FACT_TABLES,
    dimension_tables=DIMENSION_TABLES,
    timestamp_sources={
        "payments": "payment_timestamp",
        "transfers": "transfer_timestamp",
        "treasury_positions": "position_date",
        "treasury_transactions": "transaction_date",
    },
    date_columns=DATE_COLUMNS,
    numeric_columns=NUMERIC_COLUMNS,
    type_mismatch_columns=TYPE_MISMATCH_COLUMNS,
    event_definitions=(
        EventDefinition("payment_event", "payments", "PAYMENT_COMPLETED", "payment_id", "payment_timestamp"),
        EventDefinition("transfer_event", "transfers", "TRANSFER_COMPLETED", "transfer_id", "transfer_timestamp"),
        EventDefinition("treasury_event", "treasury_transactions", "TREASURY_UPDATED", "treasury_txn_id", "transaction_date"),
        EventDefinition("fraud_event", "payments", "FRAUD_SIGNAL", "payment_id", "payment_timestamp", sample_every=25),
    ),
    cdc_tables=("deposit_accounts", "payments", "transfers", "treasury_positions", "treasury_transactions"),
    business_rules=BUSINESS_RULES,
)
