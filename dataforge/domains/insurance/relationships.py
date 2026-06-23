from __future__ import annotations

RELATIONSHIPS = (
    ("policies", "customer_id", "customers", "customer_id"),
    ("policies", "agent_id", "agents", "agent_id"),
    ("premiums", "policy_id", "policies", "policy_id"),
    ("claims", "policy_id", "policies", "policy_id"),
    ("claims", "customer_id", "customers", "customer_id"),
    ("settlements", "claim_id", "claims", "claim_id"),
)
