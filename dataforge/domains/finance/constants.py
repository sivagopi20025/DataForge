from __future__ import annotations

CUSTOMER_SEGMENTS = ("Retail", "Premium", "Business")
ACCOUNT_TYPES = ("Savings", "Checking", "Business", "Loan")
ACCOUNT_STATUSES = ("Active", "Inactive", "Frozen", "Closed")
TRANSACTION_TYPES = ("Credit", "Debit", "Transfer", "Withdrawal", "Deposit")
TRANSACTION_STATUSES = ("Success", "Pending", "Failed", "Reversed")
CARD_TYPES = ("Debit", "Credit")
CARD_NETWORKS = ("Visa", "Mastercard", "Amex", "Discover")
CARD_STATUSES = ("Active", "Inactive", "Blocked", "Expired")
LOAN_TYPES = ("Home", "Auto", "Personal", "Education")
LOAN_STATUSES = ("Active", "Closed", "Defaulted")
PAYMENT_STATUSES = ("Pending", "Paid", "Failed", "Partial")
FRAUD_SCENARIOS = ("large_transaction", "rapid_transactions", "duplicate_transaction", "cross_country", "suspicious_merchant")
TRADE_SIDES = ("Buy", "Sell")
TRADE_STATUSES = ("Executed", "Pending", "Rejected", "Cancelled", "Settled")
POSITION_STATUSES = ("Open", "Closed", "Restricted")
MARKET_STATUSES = ("Open", "Closed", "Halted")
RISK_CATEGORIES = ("Low", "Medium", "High", "Critical")
RISK_STATUSES = ("Open", "Reviewed", "Closed")
RISK_REASONS = ("price_volatility", "large_notional", "concentration_limit", "market_halt", "manual_review")
INSTRUMENT_SYMBOLS = ("AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "SPY", "QQQ", "BND", "VTI", "NVDA")

CITIES = (
    ("Atlanta", "GA", "USA"),
    ("Austin", "TX", "USA"),
    ("Boston", "MA", "USA"),
    ("Chicago", "IL", "USA"),
    ("Seattle", "WA", "USA"),
)
FIRST_NAMES = ("Ava", "Liam", "Mia", "Noah", "Emma", "Ethan", "Zoe", "Lucas")
LAST_NAMES = ("Patel", "Smith", "Chen", "Garcia", "Brown", "Wilson", "Kim", "Davis")
MERCHANTS = ("DataForge Market", "Northwind Fuel", "Contoso Travel", "Fabrikam Health", "Adventure Works", "Tailspin Cafe")
