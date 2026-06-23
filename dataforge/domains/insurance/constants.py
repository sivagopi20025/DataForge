from __future__ import annotations

CUSTOMER_SEGMENTS = ("Individual", "Family", "Business", "Enterprise")
AGENT_STATUSES = ("Active", "Inactive", "Suspended")
POLICY_TYPES = ("Auto", "Home", "Health", "Life", "Travel", "Commercial")
POLICY_STATUSES = ("Active", "Expired", "Cancelled", "Suspended")
PREMIUM_STATUSES = ("Pending", "Paid", "Overdue", "Cancelled")
CLAIM_TYPES = ("Accident", "Medical", "Property Damage", "Death Benefit", "Theft", "Natural Disaster")
CLAIM_STATUSES = ("Submitted", "Under Review", "Approved", "Rejected", "Settled")
SETTLEMENT_STATUSES = ("Pending", "Approved", "Paid", "Rejected")
FRAUD_SCENARIOS = (
    "duplicate_claims",
    "multiple_claims_short_time",
    "high_value_claim",
    "cross_region_claim",
    "suspicious_settlement",
    "rapid_policy_creation_cancellation",
)

CITIES = (
    ("Atlanta", "GA", "Southeast", "USA"),
    ("Austin", "TX", "Southwest", "USA"),
    ("Boston", "MA", "Northeast", "USA"),
    ("Chicago", "IL", "Midwest", "USA"),
    ("Seattle", "WA", "West", "USA"),
)
FIRST_NAMES = ("Ava", "Liam", "Mia", "Noah", "Emma", "Ethan", "Zoe", "Lucas")
LAST_NAMES = ("Patel", "Smith", "Chen", "Garcia", "Brown", "Wilson", "Kim", "Davis")
