from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from ...audit import enrich_dataset
from ...model import Dataset
from .constants import (
    CITIES,
    CLAIM_STATUSES,
    CPT_CODES,
    FIRST_NAMES,
    ICD10_CODES,
    LAST_NAMES,
    PAYMENT_STATUSES,
    SEVERITIES,
    SPECIALTIES,
    VISIT_STATUSES,
    VISIT_TYPES,
)
from .schemas import HEALTHCARE_SPEC


class HealthcareGenerator:
    def __init__(self, visit_records: int, seed: int = 42, load_type: str = "bulk", scd_type: int = 1) -> None:
        if visit_records < 1:
            raise ValueError("records must be at least 1")
        self.visit_records = visit_records
        self.rng = random.Random(seed)
        self.load_type = load_type
        self.scd_type = scd_type
        self.today = date(2026, 6, 22)
        self.selected_tables: set[str] | None = None

    def _count(self, ratio: float, minimum: int, maximum: int | None = None) -> int:
        value = max(minimum, int(self.visit_records * ratio))
        return min(value, maximum) if maximum else value

    def _person(self, number: int) -> tuple[str, str]:
        return FIRST_NAMES[number % len(FIRST_NAMES)], LAST_NAMES[(number * 3) % len(LAST_NAMES)]

    def generate(self) -> Dataset:
        selected = self.selected_tables
        full = not selected

        def need(table: str) -> bool:
            return full or table in selected

        need_visits = full or bool(selected & {"visits", "diagnoses", "procedures", "claims", "payments"})
        need_patients = full or bool(selected & {"patients", "visits", "diagnoses", "procedures", "claims", "payments"})
        need_providers = full or bool(selected & {"providers", "visits", "diagnoses", "procedures", "claims", "payments"})
        need_claims = full or bool(selected & {"claims", "payments"})

        patient_count = min(75000, self._count(0.20, 100))
        provider_count = min(5000, self._count(0.01, 20))
        start = datetime(2026, 6, 21) if self.load_type in {"incremental", "delta", "cdc", "event", "event_stream"} else datetime(2026, 1, 1)
        data: Dataset = {}

        if need_patients:
            data["patients"] = []
            genders = ("Female", "Male", "Nonbinary")
            for i in range(1, patient_count + 1):
                first, last = self._person(i)
                city, state = CITIES[i % len(CITIES)]
                age = i % 101
                dob = self.today.replace(year=self.today.year - age) - timedelta(days=i % 365)
                data["patients"].append({
                    "patient_id": 1000000 + i,
                    "first_name": first,
                    "last_name": last,
                    "gender": genders[i % len(genders)],
                    "dob": dob.isoformat(),
                    "phone": f"555-{i % 1000:03d}-{(i * 29) % 10000:04d}",
                    "email": f"{first}.{last}.{i}@patient.example.test".lower(),
                    "city": city,
                    "state": state,
                    "country": "USA",
                    "created_at": str(self.today - timedelta(days=30 + i % 2500)),
                })

        if need_providers:
            data["providers"] = []
            for i in range(1, provider_count + 1):
                city, state = CITIES[(i + 2) % len(CITIES)]
                data["providers"].append({
                    "provider_id": 2000000 + i,
                    "provider_name": f"{SPECIALTIES[i % len(SPECIALTIES)]} Provider {i:05d}",
                    "specialty": SPECIALTIES[i % len(SPECIALTIES)],
                    "city": city,
                    "state": state,
                    "country": "USA",
                    "npi_number": f"{1000000000 + i}",
                    "created_at": str(self.today - timedelta(days=90 + i % 3000)),
                })

        if need_visits:
            data["visits"] = []
            for i in range(1, self.visit_records + 1):
                visit_date = start + timedelta(minutes=i * 11)
                data["visits"].append({
                    "visit_id": 3000000 + i,
                    "patient_id": data["patients"][self.rng.randrange(len(data["patients"]))]["patient_id"],
                    "provider_id": data["providers"][i % len(data["providers"])]["provider_id"],
                    "visit_date": visit_date.isoformat(),
                    "visit_type": VISIT_TYPES[i % len(VISIT_TYPES)],
                    "visit_status": VISIT_STATUSES[i % len(VISIT_STATUSES)],
                })

        if need("diagnoses"):
            data["diagnoses"] = []
            for i, visit in enumerate(data["visits"], 1):
                code, description = ICD10_CODES[i % len(ICD10_CODES)]
                data["diagnoses"].append({
                    "diagnosis_id": 4000000 + i,
                    "visit_id": visit["visit_id"],
                    "icd10_code": code,
                    "diagnosis_description": description,
                    "severity": SEVERITIES[i % len(SEVERITIES)],
                })

        if need("procedures"):
            data["procedures"] = []
            for i, visit in enumerate(data["visits"], 1):
                code, description = CPT_CODES[i % len(CPT_CODES)]
                cost = Decimal(75 + (i % 1500)) + (Decimal(self.rng.randrange(0, 100)) / 100)
                data["procedures"].append({
                    "procedure_id": 5000000 + i,
                    "visit_id": visit["visit_id"],
                    "cpt_code": code,
                    "procedure_description": description,
                    "procedure_cost": str(cost.quantize(Decimal("0.01"))),
                })

        if need_claims:
            data["claims"] = []
            for i, visit in enumerate(data["visits"], 1):
                amount = Decimal(125 + (i % 5000)) + (Decimal(self.rng.randrange(0, 100)) / 100)
                status = CLAIM_STATUSES[i % len(CLAIM_STATUSES)]
                submitted = datetime.fromisoformat(visit["visit_date"]) + timedelta(days=1 + i % 5)
                data["claims"].append({
                    "claim_id": 6000000 + i,
                    "patient_id": visit["patient_id"],
                    "visit_id": visit["visit_id"],
                    "provider_id": visit["provider_id"],
                    "claim_amount": str(amount.quantize(Decimal("0.01"))),
                    "claim_status": status,
                    "submitted_date": submitted.isoformat(),
                })

        if need("payments"):
            data["payments"] = []
            payment_status_by_claim = {
                "Submitted": "Pending",
                "Pending": "Pending",
                "Approved": "Partial",
                "Denied": "Rejected",
                "Paid": "Paid",
            }
            for i, claim in enumerate(data["claims"], 1):
                status = payment_status_by_claim[claim["claim_status"]]
                if status == "Rejected":
                    amount = Decimal("0.00")
                elif status == "Partial":
                    amount = (Decimal(str(claim["claim_amount"])) * Decimal("0.50")).quantize(Decimal("0.01"))
                elif status == "Paid":
                    amount = Decimal(str(claim["claim_amount"]))
                else:
                    amount = Decimal("0.00")
                payment_date = datetime.fromisoformat(claim["submitted_date"]) + timedelta(days=3 + i % 14)
                data["payments"].append({
                    "payment_id": 7000000 + i,
                    "claim_id": claim["claim_id"],
                    "payment_amount": str(amount),
                    "payment_date": payment_date.isoformat(),
                    "payment_status": status if status in PAYMENT_STATUSES else "Pending",
                })

        return enrich_dataset(data, self.load_type, self.scd_type, HEALTHCARE_SPEC)
