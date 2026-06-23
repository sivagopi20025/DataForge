from __future__ import annotations

SPECIALTIES = (
    "Cardiology",
    "Orthopedics",
    "Internal Medicine",
    "Emergency",
    "Neurology",
    "Pediatrics",
)

VISIT_TYPES = ("Emergency", "Outpatient", "Inpatient", "Telehealth")
VISIT_STATUSES = ("Completed", "Cancelled", "No Show")
SEVERITIES = ("Low", "Medium", "High", "Critical")
CLAIM_STATUSES = ("Submitted", "Pending", "Approved", "Denied", "Paid")
PAYMENT_STATUSES = ("Pending", "Paid", "Partial", "Rejected")

ICD10_CODES = (
    ("I10", "Essential hypertension"),
    ("E11.9", "Type 2 diabetes mellitus without complications"),
    ("J06.9", "Acute upper respiratory infection"),
    ("M54.5", "Low back pain"),
    ("R07.9", "Chest pain, unspecified"),
    ("G43.909", "Migraine, unspecified"),
)

CPT_CODES = (
    ("99213", "Office outpatient visit"),
    ("99284", "Emergency department visit"),
    ("93000", "Electrocardiogram"),
    ("80053", "Comprehensive metabolic panel"),
    ("97110", "Therapeutic exercises"),
    ("70450", "CT head without contrast"),
)

CITIES = (
    ("Atlanta", "GA"),
    ("Austin", "TX"),
    ("Boston", "MA"),
    ("Chicago", "IL"),
    ("Seattle", "WA"),
)

FIRST_NAMES = ("Ava", "Liam", "Mia", "Noah", "Emma", "Ethan", "Zoe", "Lucas")
LAST_NAMES = ("Patel", "Smith", "Chen", "Garcia", "Brown", "Wilson", "Kim", "Davis")
