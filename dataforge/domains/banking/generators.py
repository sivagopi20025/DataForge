from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from ...audit import enrich_dataset
from ...model import Dataset
from ...synthetic_values import business_name, full_name
from .constants import (
    ACCOUNT_STATUSES,
    ACCOUNT_TYPES,
    CARD_AUTHORIZATION_STATUSES,
    CARD_DECLINE_REASONS,
    CARD_RESPONSE_CODES,
    BRANCH_STATUSES,
    CITIES,
    CURRENCIES,
    CUSTOMER_TYPES,
    FRAUD_SCENARIOS,
    PAYMENT_STATUSES,
    PAYMENT_TYPES,
    RECONCILIATION_SCENARIOS,
    RISK_RATINGS,
    TRANSFER_STATUSES,
    TREASURY_TRANSACTION_TYPES,
)
from .schemas import BANKING_SPEC


class BankingGenerator:
    def __init__(self, payment_records: int, seed: int = 42, load_type: str = "bulk", scd_type: int = 1) -> None:
        if payment_records < 1:
            raise ValueError("records must be at least 1")
        self.payment_records = payment_records
        self.rng = random.Random(seed)
        self.load_type = load_type
        self.scd_type = scd_type
        self.today = date(2026, 6, 22)
        self.selected_tables: set[str] | None = None

    def _count(self, ratio: float, minimum: int, maximum: int | None = None) -> int:
        value = max(minimum, int(self.payment_records * ratio))
        return min(value, maximum) if maximum else value

    def _customer_name(self, index: int, customer_type: str) -> str:
        if customer_type == "Individual":
            return full_name(index, "banking.customer")
        suffixes = {
            "Business": ("Banking Services", "Treasury Services", "Operating Company", "Merchant Group"),
            "Corporate": ("Holdings", "Capital Partners", "Global Finance", "Enterprise Group"),
            "Government": ("Municipal Authority", "Public Finance", "Treasury Office", "Civic Trust"),
        }
        suffix_pool = suffixes.get(customer_type, ("Financial Services",))
        suffix = suffix_pool[(index - 1) % len(suffix_pool)]
        return business_name(index, f"banking.{customer_type.lower()}", suffix, include_index=False)

    def generate(self) -> Dataset:
        selected = self.selected_tables
        full = not selected

        def need(table: str) -> bool:
            return full or table in selected

        need_customers = full or bool(selected & {"customers", "deposit_accounts", "payments", "transfers", "card_authorizations"})
        need_branches = full or bool(selected & {"branches", "deposit_accounts", "payments", "transfers", "card_authorizations", "treasury_positions", "treasury_transactions"})
        need_accounts = full or bool(selected & {"deposit_accounts", "payments", "transfers", "card_authorizations"})
        need_positions = full or bool(selected & {"treasury_positions", "treasury_transactions"})

        customer_count = min(75000, self._count(0.20, 100))
        branch_count = min(5000, self._count(0.01, 20))
        account_count = min(125000, self._count(0.35, 150))
        position_count = min(50000, self._count(0.08, 25))
        authorization_count = min(200000, self._count(0.60, 40))
        start = datetime(2026, 6, 21) if self.load_type in {"incremental", "delta", "cdc", "event", "event_stream"} else datetime(2026, 1, 1)
        data: Dataset = {}

        if need_customers:
            data["customers"] = []
            for i in range(1, customer_count + 1):
                city, state, _, country = CITIES[i % len(CITIES)]
                data["customers"].append({
                    "customer_id": 1300000 + i,
                    "customer_type": CUSTOMER_TYPES[i % len(CUSTOMER_TYPES)],
                    "customer_name": self._customer_name(i, CUSTOMER_TYPES[i % len(CUSTOMER_TYPES)]),
                    "country": country,
                    "state": state,
                    "city": city,
                    "risk_rating": RISK_RATINGS[i % len(RISK_RATINGS)],
                    "created_at": str(self.today - timedelta(days=60 + i % 3000)),
                })

        if need_branches:
            data["branches"] = []
            for i in range(1, branch_count + 1):
                city, state, region, country = CITIES[i % len(CITIES)]
                data["branches"].append({
                    "branch_id": 2300000 + i,
                    "branch_name": f"{city} Branch {i:04d}",
                    "branch_code": f"BR-{i:06d}",
                    "country": country,
                    "state": state,
                    "city": city,
                    "region": region,
                    "status": BRANCH_STATUSES[i % len(BRANCH_STATUSES)] if i % 29 == 0 else "Active",
                })

        if need_accounts:
            data["deposit_accounts"] = []
            for i in range(1, account_count + 1):
                status = "Active" if i % 17 else ACCOUNT_STATUSES[i % len(ACCOUNT_STATUSES)]
                currency = CURRENCIES[i % len(CURRENCIES)]
                balance = Decimal(1000 + (i % 75000)) + Decimal(self.rng.randrange(0, 100)) / 100
                data["deposit_accounts"].append({
                    "account_id": 3300000 + i,
                    "customer_id": data["customers"][(i - 1) % len(data["customers"])]["customer_id"],
                    "branch_id": data["branches"][i % len(data["branches"])]["branch_id"],
                    "account_type": ACCOUNT_TYPES[i % len(ACCOUNT_TYPES)],
                    "currency": currency,
                    "balance": str(balance.quantize(Decimal("0.01"))),
                    "account_status": status,
                    "opened_date": str(self.today - timedelta(days=30 + i % 2500)),
                })

        if need("payments"):
            data["payments"] = []
            active_accounts = [row for row in data["deposit_accounts"] if row["account_status"] == "Active"]
            for i in range(1, self.payment_records + 1):
                account = active_accounts[i % len(active_accounts)]
                scenario = FRAUD_SCENARIOS[i % len(FRAUD_SCENARIOS)] if i % 97 == 0 else ""
                recon = RECONCILIATION_SCENARIOS[i % len(RECONCILIATION_SCENARIOS)] if i % 131 == 0 else ""
                amount = Decimal(25 + (i % 10000)) + Decimal(self.rng.randrange(0, 100)) / 100
                if scenario == "high_value_payment":
                    amount = Decimal("50000.00")
                data["payments"].append({
                    "payment_id": 4300000 + i,
                    "account_id": account["account_id"],
                    "payment_type": PAYMENT_TYPES[i % len(PAYMENT_TYPES)],
                    "amount": str(amount.quantize(Decimal("0.01"))),
                    "currency": account["currency"],
                    "payment_status": "Completed" if i % 13 else PAYMENT_STATUSES[i % len(PAYMENT_STATUSES)],
                    "payment_timestamp": (start + timedelta(seconds=i * 5)).isoformat(),
                    "fraud_scenario": scenario or "none",
                    "is_fraud_scenario": bool(scenario),
                    "reconciliation_scenario": recon or "none",
                    "is_reconciliation_scenario": bool(recon),
                })

        if need("transfers"):
            data["transfers"] = []
            active_accounts = [row for row in data["deposit_accounts"] if row["account_status"] == "Active"]
            active_accounts_by_currency: dict[str, list[dict]] = {}
            for account in active_accounts:
                active_accounts_by_currency.setdefault(account["currency"], []).append(account)
            for i in range(1, max(1, self.payment_records // 2) + 1):
                source = active_accounts[i % len(active_accounts)]
                same_currency_accounts = active_accounts_by_currency[source["currency"]]
                destination = same_currency_accounts[(i * 3) % len(same_currency_accounts)]
                if destination["account_id"] == source["account_id"]:
                    destination = same_currency_accounts[(i * 3 + 1) % len(same_currency_accounts)] if len(same_currency_accounts) > 1 else active_accounts[(i + 1) % len(active_accounts)]
                recon = RECONCILIATION_SCENARIOS[i % len(RECONCILIATION_SCENARIOS)] if i % 149 == 0 else ""
                amount = Decimal(50 + (i % 20000)) + Decimal(self.rng.randrange(0, 100)) / 100
                data["transfers"].append({
                    "transfer_id": 5300000 + i,
                    "source_account_id": source["account_id"],
                    "destination_account_id": destination["account_id"],
                    "transfer_amount": str(amount.quantize(Decimal("0.01"))),
                    "currency": source["currency"],
                    "transfer_status": "Completed" if i % 11 else TRANSFER_STATUSES[i % len(TRANSFER_STATUSES)],
                    "transfer_timestamp": (start + timedelta(seconds=i * 11)).isoformat(),
                    "reconciliation_scenario": recon or "none",
                    "is_reconciliation_scenario": bool(recon),
                })

        if need("card_authorizations"):
            data["card_authorizations"] = []
            active_accounts = [row for row in data["deposit_accounts"] if row["account_status"] == "Active"]
            customers_by_id = {row["customer_id"]: row for row in data["customers"]}
            merchant_categories = ("grocery", "fuel", "travel", "restaurant", "electronics", "healthcare")
            for i in range(1, authorization_count + 1):
                account = active_accounts[(i - 1) % len(active_accounts)]
                customer = customers_by_id[account["customer_id"]]
                authorized_at = start + timedelta(seconds=i * 7)
                base_amount = Decimal(5 + (i % 1800)) + Decimal(self.rng.randrange(0, 100)) / 100
                if i % 97 == 0:
                    status = "Declined"
                    response_code = CARD_RESPONSE_CODES[i % len(CARD_RESPONSE_CODES)]
                    reason_code = CARD_DECLINE_REASONS[(i % (len(CARD_DECLINE_REASONS) - 1)) + 1]
                elif i % 31 == 0:
                    status = "Expired"
                    response_code = "00"
                    reason_code = "not_applicable"
                elif i % 23 == 0:
                    status = "Reversed"
                    response_code = "00"
                    reason_code = "not_applicable"
                else:
                    status = "Captured" if i % 3 else "Approved"
                    response_code = "00"
                    reason_code = "not_applicable"
                expires_at = authorized_at + timedelta(days=7)
                captured_at = authorized_at + timedelta(minutes=5 + i % 240)
                data["card_authorizations"].append({
                    "card_authorization_id": 8300000 + i,
                    "account_id": account["account_id"],
                    "customer_id": customer["customer_id"],
                    "branch_id": account["branch_id"],
                    "merchant_name": f"{merchant_categories[i % len(merchant_categories)].title()} Merchant {i % 5000:04d}",
                    "authorization_amount": str(base_amount.quantize(Decimal("0.01"))),
                    "currency": account["currency"],
                    "authorization_timestamp": authorized_at.isoformat(),
                    "authorization_status": status,
                    "response_code": response_code,
                    "reason_code": reason_code,
                    "expires_at": expires_at.isoformat(),
                    "captured_at": captured_at.isoformat() if status == "Captured" else "not_applicable",
                    "external_reference": f"AUTH-{authorized_at:%Y%m%d}-{i:010d}",
                    "capture_reference": f"CAP-{i:010d}" if status == "Captured" else "not_applicable",
                })

        if need_positions:
            data["treasury_positions"] = []
            for i in range(1, position_count + 1):
                cash = Decimal(100000 + (i % 1000000)) + Decimal(self.rng.randrange(0, 100)) / 100
                data["treasury_positions"].append({
                    "position_id": 6300000 + i,
                    "branch_id": data["branches"][i % len(data["branches"])]["branch_id"],
                    "position_date": (start + timedelta(days=i % 30)).isoformat(),
                    "currency": CURRENCIES[i % len(CURRENCIES)],
                    "cash_position": str(cash.quantize(Decimal("0.01"))),
                    "liquidity_ratio": str((Decimal("0.10") + Decimal(i % 80) / 100).quantize(Decimal("0.01"))),
                    "market_value": str((cash * Decimal("1.05")).quantize(Decimal("0.01"))),
                })

        if need("treasury_transactions"):
            data["treasury_transactions"] = []
            for i, position in enumerate(data["treasury_positions"], 1):
                amount = Decimal(5000 + (i % 250000)) + Decimal(self.rng.randrange(0, 100)) / 100
                data["treasury_transactions"].append({
                    "treasury_txn_id": 7300000 + i,
                    "position_id": position["position_id"],
                    "transaction_type": TREASURY_TRANSACTION_TYPES[i % len(TREASURY_TRANSACTION_TYPES)],
                    "transaction_amount": str(amount.quantize(Decimal("0.01"))),
                    "transaction_date": (datetime.fromisoformat(position["position_date"]) + timedelta(hours=i % 24)).isoformat(),
                })

        return enrich_dataset(data, self.load_type, self.scd_type, BANKING_SPEC)
