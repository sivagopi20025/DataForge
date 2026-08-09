from __future__ import annotations

CUSTOMER_TYPES = ("Individual", "Business", "Corporate", "Government")
RISK_RATINGS = ("Low", "Medium", "High", "Critical")
BRANCH_STATUSES = ("Active", "Inactive", "Merged")
ACCOUNT_TYPES = ("Savings", "Checking", "Corporate", "Term Deposit")
ACCOUNT_STATUSES = ("Active", "Dormant", "Closed", "Frozen")
PAYMENT_TYPES = ("ACH", "Wire", "RTGS", "NEFT", "UPI", "SWIFT")
PAYMENT_STATUSES = ("Pending", "Completed", "Failed", "Cancelled")
TRANSFER_STATUSES = ("Initiated", "Processing", "Completed", "Failed", "Reversed")
TREASURY_TRANSACTION_TYPES = ("Buy", "Sell", "Transfer", "Hedge")
CARD_AUTHORIZATION_STATUSES = ("Requested", "Approved", "Declined", "Captured", "Expired", "Reversed")
CARD_RESPONSE_CODES = ("00", "05", "51", "54", "91")
CARD_DECLINE_REASONS = ("not_applicable", "insufficient_funds", "do_not_honor", "expired_card", "issuer_unavailable")
CURRENCIES = ("USD", "EUR", "GBP", "INR", "JPY")
FRAUD_SCENARIOS = ("high_value_payment", "rapid_transfers", "duplicate_payment", "cross_currency", "suspicious_treasury")
RECONCILIATION_SCENARIOS = ("expected_balance", "actual_balance", "missing_transaction", "duplicate_transaction", "reversed_transaction", "settlement_mismatch")

CITIES = (
    ("Atlanta", "GA", "Southeast", "USA"),
    ("Austin", "TX", "Southwest", "USA"),
    ("Boston", "MA", "Northeast", "USA"),
    ("Chicago", "IL", "Midwest", "USA"),
    ("Seattle", "WA", "West", "USA"),
)
