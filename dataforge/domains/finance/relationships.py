from __future__ import annotations

RELATIONSHIPS = (
    ("accounts", "customer_id", "customers", "customer_id"),
    ("transactions", "account_id", "accounts", "account_id"),
    ("cards", "customer_id", "customers", "customer_id"),
    ("cards", "account_id", "accounts", "account_id"),
    ("loans", "customer_id", "customers", "customer_id"),
    ("payments", "loan_id", "loans", "loan_id"),
    ("payments", "customer_id", "customers", "customer_id"),
)
