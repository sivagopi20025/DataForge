from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from ...audit import enrich_dataset
from ...model import Dataset
from ...synthetic_values import full_name, person_name, unique_email
from .constants import (
    AGENT_STATUSES,
    CITIES,
    CLAIM_STATUSES,
    CLAIM_TYPES,
    CUSTOMER_SEGMENTS,
    FIRST_NAMES,
    FRAUD_SCENARIOS,
    LAST_NAMES,
    POLICY_STATUSES,
    POLICY_TYPES,
    PREMIUM_STATUSES,
    SETTLEMENT_STATUSES,
)
from .schemas import INSURANCE_SPEC


class InsuranceGenerator:
    def __init__(self, claim_records: int, seed: int = 42, load_type: str = "bulk", scd_type: int = 1) -> None:
        if claim_records < 1:
            raise ValueError("records must be at least 1")
        self.claim_records = claim_records
        self.rng = random.Random(seed)
        self.load_type = load_type
        self.scd_type = scd_type
        self.today = date(2026, 6, 22)
        self.selected_tables: set[str] | None = None

    def _count(self, ratio: float, minimum: int, maximum: int | None = None) -> int:
        value = max(minimum, int(self.claim_records * ratio))
        return min(value, maximum) if maximum else value

    def _person(self, number: int) -> tuple[str, str]:
        return person_name(number, "insurance")

    def generate(self) -> Dataset:
        selected = self.selected_tables
        full = not selected

        def need(table: str) -> bool:
            return full or table in selected

        need_customers = full or bool(selected & {"customers", "policies", "premiums", "claims", "settlements"})
        need_agents = full or bool(selected & {"agents", "policies", "premiums", "claims", "settlements"})
        need_policies = full or bool(selected & {"policies", "premiums", "claims", "settlements"})
        need_claims = full or bool(selected & {"claims", "settlements"})

        customer_count = min(75000, self._count(0.20, 100))
        agent_count = min(5000, self._count(0.01, 20))
        policy_count = min(125000, self._count(0.35, 150))
        start = datetime(2026, 6, 21) if self.load_type in {"incremental", "delta", "cdc", "event", "event_stream"} else datetime(2026, 1, 1)
        data: Dataset = {}

        if need_customers:
            data["customers"] = []
            genders = ("Female", "Male", "Nonbinary")
            for i in range(1, customer_count + 1):
                first, last = self._person(i)
                city, state, _, country = CITIES[i % len(CITIES)]
                age = 18 + (i % 73)
                dob = self.today.replace(year=self.today.year - age) - timedelta(days=i % 365)
                data["customers"].append({
                    "customer_id": 1200000 + i,
                    "first_name": first,
                    "last_name": last,
                    "dob": dob.isoformat(),
                    "gender": genders[i % len(genders)],
                    "email": unique_email(first, last, 1200000 + i, "insurance.customer"),
                    "phone": f"555-{i % 1000:03d}-{(i * 37) % 10000:04d}",
                    "city": city,
                    "state": state,
                    "country": country,
                    "customer_segment": CUSTOMER_SEGMENTS[i % len(CUSTOMER_SEGMENTS)],
                    "created_at": str(self.today - timedelta(days=60 + i % 3000)),
                })

        if need_agents:
            data["agents"] = []
            for i in range(1, agent_count + 1):
                _, _, region, _ = CITIES[i % len(CITIES)]
                data["agents"].append({
                    "agent_id": 2200000 + i,
                    "agent_name": full_name(i + 4, "insurance.agent"),
                    "agent_region": region,
                    "agent_status": AGENT_STATUSES[i % len(AGENT_STATUSES)] if i % 23 == 0 else "Active",
                    "hire_date": str(self.today - timedelta(days=100 + i % 2600)),
                    "license_number": f"INS-{i:09d}",
                })

        if need_policies:
            data["policies"] = []
            for i in range(1, policy_count + 1):
                policy_start = self.today - timedelta(days=30 + i % 1800)
                status = "Active" if i % 13 else POLICY_STATUSES[i % len(POLICY_STATUSES)]
                coverage = Decimal(10000 + (i % 500000)) + Decimal(self.rng.randrange(0, 100)) / 100
                premium = (coverage * Decimal("0.012")).quantize(Decimal("0.01"))
                data["policies"].append({
                    "policy_id": 3200000 + i,
                    "customer_id": data["customers"][(i - 1) % len(data["customers"])]["customer_id"],
                    "agent_id": data["agents"][i % len(data["agents"])]["agent_id"],
                    "policy_type": POLICY_TYPES[i % len(POLICY_TYPES)],
                    "policy_status": status,
                    "policy_start_date": policy_start.isoformat(),
                    "policy_end_date": (policy_start + timedelta(days=365)).isoformat(),
                    "coverage_amount": str(coverage.quantize(Decimal("0.01"))),
                    "premium_amount": str(premium),
                })

        if need("premiums"):
            data["premiums"] = []
            premium_id = 1
            for policy in data["policies"]:
                if policy["policy_status"] == "Cancelled":
                    continue
                due_date = datetime.fromisoformat(policy["policy_start_date"]) + timedelta(days=30)
                status = PREMIUM_STATUSES[premium_id % len(PREMIUM_STATUSES)] if premium_id % 17 == 0 else "Paid"
                data["premiums"].append({
                    "premium_id": 4200000 + premium_id,
                    "policy_id": policy["policy_id"],
                    "premium_amount": policy["premium_amount"],
                    "due_date": due_date.isoformat(),
                    "payment_date": (due_date + timedelta(days=2)).isoformat(),
                    "premium_status": status,
                })
                premium_id += 1

        if need_claims:
            data["claims"] = []
            active_policies = [row for row in data["policies"] if row["policy_status"] == "Active"]
            for i in range(1, self.claim_records + 1):
                policy = active_policies[i % len(active_policies)]
                scenario = FRAUD_SCENARIOS[i % len(FRAUD_SCENARIOS)] if i % 89 == 0 else ""
                coverage = Decimal(str(policy["coverage_amount"]))
                amount = (coverage * Decimal("0.10") + Decimal(i % 5000)).quantize(Decimal("0.01"))
                if scenario == "high_value_claim":
                    amount = (coverage * Decimal("0.85")).quantize(Decimal("0.01"))
                claim_date = start + timedelta(minutes=i * 13)
                data["claims"].append({
                    "claim_id": 5200000 + i,
                    "policy_id": policy["policy_id"],
                    "customer_id": policy["customer_id"],
                    "claim_amount": str(min(amount, coverage).quantize(Decimal("0.01"))),
                    "claim_type": CLAIM_TYPES[i % len(CLAIM_TYPES)],
                    "claim_status": CLAIM_STATUSES[i % len(CLAIM_STATUSES)] if i % 11 == 0 else "Approved",
                    "claim_date": claim_date.isoformat(),
                    "fraud_scenario": scenario or "none",
                    "is_fraud_scenario": bool(scenario),
                })

        if need("settlements"):
            data["settlements"] = []
            approved_claims = [row for row in data["claims"] if row["claim_status"] in {"Approved", "Settled"}]
            for i, claim in enumerate(approved_claims, 1):
                claim_amount = Decimal(str(claim["claim_amount"]))
                status = SETTLEMENT_STATUSES[i % len(SETTLEMENT_STATUSES)] if i % 19 == 0 else "Paid"
                amount = claim_amount if status == "Paid" else (claim_amount * Decimal("0.75")).quantize(Decimal("0.01"))
                settlement_date = datetime.fromisoformat(claim["claim_date"]) + timedelta(days=5 + i % 30)
                data["settlements"].append({
                    "settlement_id": 6200000 + i,
                    "claim_id": claim["claim_id"],
                    "settlement_amount": str(amount),
                    "settlement_date": settlement_date.isoformat(),
                    "settlement_status": status,
                })

        return enrich_dataset(data, self.load_type, self.scd_type, INSURANCE_SPEC)
