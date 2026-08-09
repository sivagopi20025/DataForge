from __future__ import annotations

DATE_COLUMNS = {
    "patients": "created_at",
    "providers": "created_at",
    "visits": "visit_date",
    "prior_authorizations": "requested_at",
    "claims": "submitted_date",
    "payments": "payment_date",
}

NUMERIC_COLUMNS = {
    "procedures": "procedure_cost",
    "prior_authorizations": "approved_amount",
    "claims": "claim_amount",
    "payments": "payment_amount",
}

TYPE_MISMATCH_COLUMNS = {
    "patients": "first_name",
    "providers": "npi_number",
    "visits": "visit_type",
    "diagnoses": "icd10_code",
    "procedures": "cpt_code",
    "prior_authorizations": "authorization_status",
    "claims": "claim_status",
    "payments": "payment_status",
}
