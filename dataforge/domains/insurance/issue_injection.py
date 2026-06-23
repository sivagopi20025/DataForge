from __future__ import annotations

DATE_COLUMNS = {
    "customers": "created_at",
    "agents": "hire_date",
    "policies": "policy_start_date",
    "premiums": "due_date",
    "claims": "claim_date",
    "settlements": "settlement_date",
}

NUMERIC_COLUMNS = {
    "policies": "coverage_amount",
    "premiums": "premium_amount",
    "claims": "claim_amount",
    "settlements": "settlement_amount",
}

TYPE_MISMATCH_COLUMNS = {
    "customers": "first_name",
    "agents": "agent_status",
    "policies": "policy_status",
    "premiums": "premium_status",
    "claims": "claim_status",
    "settlements": "settlement_status",
}
