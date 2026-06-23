from __future__ import annotations

from ...model import DomainSpec, EventDefinition, ForeignKey, TableSchema, with_enterprise_columns
from .issue_injection import DATE_COLUMNS, NUMERIC_COLUMNS, TYPE_MISMATCH_COLUMNS
from .validations import BUSINESS_RULES


BASE_SCHEMAS: dict[str, TableSchema] = {
    "customers": TableSchema("customer_id", ("customer_id", "first_name", "last_name", "dob", "gender", "email", "phone", "city", "state", "country", "customer_segment", "created_at")),
    "agents": TableSchema("agent_id", ("agent_id", "agent_name", "agent_region", "agent_status", "hire_date", "license_number")),
    "policies": TableSchema("policy_id", ("policy_id", "customer_id", "agent_id", "policy_type", "policy_status", "policy_start_date", "policy_end_date", "coverage_amount", "premium_amount"), (ForeignKey("customer_id", "customers", "customer_id"), ForeignKey("agent_id", "agents", "agent_id"))),
    "premiums": TableSchema("premium_id", ("premium_id", "policy_id", "premium_amount", "due_date", "payment_date", "premium_status"), (ForeignKey("policy_id", "policies", "policy_id"),)),
    "claims": TableSchema("claim_id", ("claim_id", "policy_id", "customer_id", "claim_amount", "claim_type", "claim_status", "claim_date", "fraud_scenario", "is_fraud_scenario"), (ForeignKey("policy_id", "policies", "policy_id"), ForeignKey("customer_id", "customers", "customer_id"))),
    "settlements": TableSchema("settlement_id", ("settlement_id", "claim_id", "settlement_amount", "settlement_date", "settlement_status"), (ForeignKey("claim_id", "claims", "claim_id"),)),
}

FACT_TABLES = {"premiums", "claims", "settlements"}
DIMENSION_TABLES = {"customers", "agents", "policies"}


INSURANCE_SPEC = DomainSpec(
    name="insurance",
    source_system="DATAFORGE_INSURANCE",
    schemas=with_enterprise_columns(BASE_SCHEMAS, FACT_TABLES, DIMENSION_TABLES),
    fact_tables=FACT_TABLES,
    dimension_tables=DIMENSION_TABLES,
    timestamp_sources={
        "premiums": "due_date",
        "claims": "claim_date",
        "settlements": "settlement_date",
    },
    date_columns=DATE_COLUMNS,
    numeric_columns=NUMERIC_COLUMNS,
    type_mismatch_columns=TYPE_MISMATCH_COLUMNS,
    event_definitions=(
        EventDefinition("policy_event", "policies", "POLICY_UPDATED", "policy_id", "updated_ts"),
        EventDefinition("claim_event", "claims", "CLAIM_UPDATED", "claim_id", "claim_date"),
        EventDefinition("settlement_event", "settlements", "SETTLEMENT_UPDATED", "settlement_id", "settlement_date"),
        EventDefinition("premium_event", "premiums", "PREMIUM_UPDATED", "premium_id", "due_date"),
        EventDefinition("fraud_event", "claims", "FRAUD_SIGNAL", "claim_id", "claim_date", sample_every=25),
    ),
    cdc_tables=("policies", "premiums", "claims", "settlements"),
    business_rules=BUSINESS_RULES,
)
