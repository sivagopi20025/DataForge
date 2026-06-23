from __future__ import annotations

RELATIONSHIPS = (
    ("deposit_accounts", "customer_id", "customers", "customer_id"),
    ("deposit_accounts", "branch_id", "branches", "branch_id"),
    ("payments", "account_id", "deposit_accounts", "account_id"),
    ("transfers", "source_account_id", "deposit_accounts", "account_id"),
    ("transfers", "destination_account_id", "deposit_accounts", "account_id"),
    ("treasury_positions", "branch_id", "branches", "branch_id"),
    ("treasury_transactions", "position_id", "treasury_positions", "position_id"),
)
