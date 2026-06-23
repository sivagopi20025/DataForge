from __future__ import annotations

RELATIONSHIPS = (
    ("visits", "patient_id", "patients", "patient_id"),
    ("visits", "provider_id", "providers", "provider_id"),
    ("diagnoses", "visit_id", "visits", "visit_id"),
    ("procedures", "visit_id", "visits", "visit_id"),
    ("claims", "patient_id", "patients", "patient_id"),
    ("claims", "visit_id", "visits", "visit_id"),
    ("claims", "provider_id", "providers", "provider_id"),
    ("payments", "claim_id", "claims", "claim_id"),
)
