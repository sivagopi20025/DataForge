from __future__ import annotations

from ...model import DomainSpec, EventDefinition, ForeignKey, TableSchema, with_enterprise_columns
from .issue_injection import DATE_COLUMNS, NUMERIC_COLUMNS, TYPE_MISMATCH_COLUMNS
from .validations import BUSINESS_RULES


BASE_SCHEMAS: dict[str, TableSchema] = {
    "patients": TableSchema("patient_id", ("patient_id", "first_name", "last_name", "gender", "dob", "phone", "email", "city", "state", "country", "created_at")),
    "providers": TableSchema("provider_id", ("provider_id", "provider_name", "specialty", "city", "state", "country", "npi_number", "created_at")),
    "visits": TableSchema("visit_id", ("visit_id", "patient_id", "provider_id", "visit_date", "visit_type", "visit_status"), (ForeignKey("patient_id", "patients", "patient_id"), ForeignKey("provider_id", "providers", "provider_id"))),
    "diagnoses": TableSchema("diagnosis_id", ("diagnosis_id", "visit_id", "icd10_code", "diagnosis_description", "severity"), (ForeignKey("visit_id", "visits", "visit_id"),)),
    "procedures": TableSchema("procedure_id", ("procedure_id", "visit_id", "cpt_code", "procedure_description", "procedure_cost"), (ForeignKey("visit_id", "visits", "visit_id"),)),
    "prior_authorizations": TableSchema("prior_authorization_id", ("prior_authorization_id", "patient_id", "provider_id", "procedure_id", "procedure_code", "requested_at", "approved_at", "authorization_status", "approved_amount", "expiration_date", "denial_reason"), (ForeignKey("patient_id", "patients", "patient_id"), ForeignKey("provider_id", "providers", "provider_id"), ForeignKey("procedure_id", "procedures", "procedure_id"))),
    "claims": TableSchema("claim_id", ("claim_id", "patient_id", "visit_id", "provider_id", "claim_amount", "claim_status", "submitted_date"), (ForeignKey("visit_id", "visits", "visit_id"), ForeignKey("patient_id", "patients", "patient_id"), ForeignKey("provider_id", "providers", "provider_id"))),
    "payments": TableSchema("payment_id", ("payment_id", "claim_id", "payment_amount", "payment_date", "payment_status"), (ForeignKey("claim_id", "claims", "claim_id"),)),
}

FACT_TABLES = {"visits", "diagnoses", "procedures", "prior_authorizations", "claims", "payments"}
DIMENSION_TABLES = {"patients", "providers"}


HEALTHCARE_SPEC = DomainSpec(
    name="healthcare",
    source_system="DATAFORGE_HEALTHCARE",
    schemas=with_enterprise_columns(BASE_SCHEMAS, FACT_TABLES, DIMENSION_TABLES),
    fact_tables=FACT_TABLES,
    dimension_tables=DIMENSION_TABLES,
    timestamp_sources={
        "visits": "visit_date",
        "prior_authorizations": "requested_at",
        "claims": "submitted_date",
        "payments": "payment_date",
    },
    date_columns=DATE_COLUMNS,
    numeric_columns=NUMERIC_COLUMNS,
    type_mismatch_columns=TYPE_MISMATCH_COLUMNS,
    event_definitions=(
        EventDefinition("visit_event", "visits", "VISIT_UPDATED", "visit_id", "visit_date"),
        EventDefinition("prior_authorization_event", "prior_authorizations", "PRIOR_AUTH_UPDATED", "prior_authorization_id", "requested_at"),
        EventDefinition("claim_event", "claims", "CLAIM_UPDATED", "claim_id", "submitted_date"),
        EventDefinition("payment_event", "payments", "PAYMENT_UPDATED", "payment_id", "payment_date"),
    ),
    cdc_tables=("patients", "visits", "prior_authorizations", "claims", "payments"),
    business_rules=BUSINESS_RULES,
)
