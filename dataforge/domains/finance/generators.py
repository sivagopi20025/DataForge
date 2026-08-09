from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from ...audit import enrich_dataset
from ...model import Dataset
from ...synthetic_values import person_name, unique_email
from .constants import (
    ACCOUNT_STATUSES,
    ACCOUNT_TYPES,
    CARD_NETWORKS,
    CARD_STATUSES,
    CARD_TYPES,
    CITIES,
    CUSTOMER_SEGMENTS,
    FIRST_NAMES,
    FRAUD_SCENARIOS,
    INSTRUMENT_SYMBOLS,
    LAST_NAMES,
    LOAN_STATUSES,
    LOAN_TYPES,
    MARKET_STATUSES,
    MERCHANTS,
    PAYMENT_STATUSES,
    POSITION_STATUSES,
    RISK_CATEGORIES,
    RISK_REASONS,
    RISK_STATUSES,
    TRADE_SIDES,
    TRADE_STATUSES,
    TRANSACTION_STATUSES,
    TRANSACTION_TYPES,
)
from .schemas import FINANCE_SPEC


class FinanceGenerator:
    def __init__(self, transaction_records: int, seed: int = 42, load_type: str = "bulk", scd_type: int = 1) -> None:
        if transaction_records < 1:
            raise ValueError("records must be at least 1")
        self.transaction_records = transaction_records
        self.rng = random.Random(seed)
        self.load_type = load_type
        self.scd_type = scd_type
        self.today = date(2026, 6, 22)
        self.selected_tables: set[str] | None = None

    def _count(self, ratio: float, minimum: int, maximum: int | None = None) -> int:
        value = max(minimum, int(self.transaction_records * ratio))
        return min(value, maximum) if maximum else value

    def _person(self, number: int) -> tuple[str, str]:
        return person_name(number, "finance")

    def generate(self) -> Dataset:
        selected = self.selected_tables
        full = not selected

        def need(table: str) -> bool:
            return full or table in selected

        need_customers = full or bool(selected & {"customers", "accounts", "transactions", "cards", "loans", "payments", "trades", "market_data", "positions", "risk_events"})
        need_accounts = full or bool(selected & {"accounts", "transactions", "cards", "trades", "market_data", "positions", "risk_events"})
        need_loans = full or bool(selected & {"loans", "payments"})
        need_risk_events = full or bool(selected & {"risk_events", "trades", "market_data", "positions"})

        customer_count = min(75000, self._count(0.20, 100))
        account_count = min(125000, self._count(0.35, 150))
        card_count = min(100000, self._count(0.20, 80))
        loan_count = min(75000, self._count(0.12, 40))
        risk_event_count = min(25000, self._count(0.04, 20))
        trade_count = self.transaction_records if full or need("trades") else 0
        market_data_count = min(50000, self._count(0.30, 100))
        position_count = min(75000, self._count(0.18, 80))
        start = datetime(2026, 6, 21) if self.load_type in {"incremental", "delta", "cdc", "event", "event_stream"} else datetime(2026, 1, 1)
        data: Dataset = {}

        if need_customers:
            data["customers"] = []
            genders = ("Female", "Male", "Nonbinary")
            for i in range(1, customer_count + 1):
                first, last = self._person(i)
                city, state, country = CITIES[i % len(CITIES)]
                age = 18 + (i % 73)
                dob = self.today.replace(year=self.today.year - age) - timedelta(days=i % 365)
                data["customers"].append({
                    "customer_id": 1100000 + i,
                    "first_name": first,
                    "last_name": last,
                    "dob": dob.isoformat(),
                    "gender": genders[i % len(genders)],
                    "email": unique_email(first, last, 1100000 + i, "finance.customer"),
                    "phone": f"555-{i % 1000:03d}-{(i * 31) % 10000:04d}",
                    "city": city,
                    "state": state,
                    "country": country,
                    "customer_segment": CUSTOMER_SEGMENTS[i % len(CUSTOMER_SEGMENTS)],
                    "created_at": str(self.today - timedelta(days=60 + i % 3000)),
                })

        if need_accounts:
            data["accounts"] = []
            for i in range(1, account_count + 1):
                account_type = ACCOUNT_TYPES[i % len(ACCOUNT_TYPES)]
                status = "Active" if i % 11 else ("Frozen" if i % 22 else "Closed")
                balance = Decimal(100 + (i % 25000)) + Decimal(self.rng.randrange(0, 100)) / 100
                if account_type == "Loan":
                    balance = Decimal(0)
                data["accounts"].append({
                    "account_id": 2100000 + i,
                    "customer_id": data["customers"][(i - 1) % len(data["customers"])]["customer_id"],
                    "account_type": account_type,
                    "account_status": status,
                    "balance": str(balance.quantize(Decimal("0.01"))),
                    "opened_date": str(self.today - timedelta(days=30 + i % 2500)),
                })

        if need("transactions"):
            data["transactions"] = []
            active_accounts = [row for row in data["accounts"] if row["account_status"] == "Active"]
            for i in range(1, self.transaction_records + 1):
                account = active_accounts[i % len(active_accounts)]
                scenario = FRAUD_SCENARIOS[i % len(FRAUD_SCENARIOS)] if i % 97 == 0 else ""
                amount = Decimal(10 + (i % 5000)) + Decimal(self.rng.randrange(0, 100)) / 100
                if scenario == "large_transaction":
                    amount = Decimal("25000.00")
                data["transactions"].append({
                    "transaction_id": 3100000 + i,
                    "account_id": account["account_id"],
                    "transaction_type": TRANSACTION_TYPES[i % len(TRANSACTION_TYPES)],
                    "transaction_amount": str(amount.quantize(Decimal("0.01"))),
                    "transaction_timestamp": (start + timedelta(seconds=i * 7)).isoformat(),
                    "merchant_name": MERCHANTS[i % len(MERCHANTS)],
                    "transaction_status": "Success" if i % 13 else TRANSACTION_STATUSES[i % len(TRANSACTION_STATUSES)],
                    "fraud_scenario": scenario or "none",
                    "is_fraud_scenario": bool(scenario),
                })

        if need("cards"):
            data["cards"] = []
            for i in range(1, card_count + 1):
                account = data["accounts"][i % len(data["accounts"])]
                data["cards"].append({
                    "card_id": 4100000 + i,
                    "customer_id": account["customer_id"],
                    "account_id": account["account_id"],
                    "card_type": CARD_TYPES[i % len(CARD_TYPES)],
                    "card_network": CARD_NETWORKS[i % len(CARD_NETWORKS)],
                    "card_status": CARD_STATUSES[i % len(CARD_STATUSES)] if i % 17 == 0 else "Active",
                    "issued_date": str(self.today - timedelta(days=10 + i % 1800)),
                })

        if need_loans:
            data["loans"] = []
            for i in range(1, loan_count + 1):
                amount = Decimal(5000 + (i % 250000)) + Decimal(self.rng.randrange(0, 100)) / 100
                data["loans"].append({
                    "loan_id": 5100000 + i,
                    "customer_id": data["customers"][(i * 3) % len(data["customers"])]["customer_id"],
                    "loan_type": LOAN_TYPES[i % len(LOAN_TYPES)],
                    "loan_amount": str(amount.quantize(Decimal("0.01"))),
                    "interest_rate": str((Decimal("2.50") + Decimal(i % 120) / 20).quantize(Decimal("0.01"))),
                    "loan_status": LOAN_STATUSES[i % len(LOAN_STATUSES)] if i % 19 == 0 else "Active",
                    "start_date": str(self.today - timedelta(days=45 + i % 2200)),
                })

        if need("payments"):
            data["payments"] = []
            for i, loan in enumerate(data["loans"], 1):
                amount = (Decimal(str(loan["loan_amount"])) / Decimal("120")).quantize(Decimal("0.01"))
                status = PAYMENT_STATUSES[i % len(PAYMENT_STATUSES)] if i % 11 == 0 else "Paid"
                data["payments"].append({
                    "payment_id": 6100000 + i,
                    "loan_id": loan["loan_id"],
                    "customer_id": loan["customer_id"],
                    "payment_amount": str(amount if status != "Failed" else Decimal("0.00")),
                    "payment_date": (start + timedelta(minutes=i * 17)).isoformat(),
                    "payment_status": status,
                })

        if need_risk_events:
            data["risk_events"] = []
            for i in range(1, risk_event_count + 1):
                account = data["accounts"][i % len(data["accounts"])]
                score = 5 + (i * 7) % 96
                category = "Critical" if score >= 85 else "High" if score >= 70 else "Medium" if score >= 40 else "Low"
                status = "Reviewed" if score >= 70 else RISK_STATUSES[i % len(RISK_STATUSES)]
                exposure = Decimal(500 + (i % 50000)) + Decimal(self.rng.randrange(0, 100)) / 100
                data["risk_events"].append({
                    "risk_event_id": 7100000 + i,
                    "account_id": account["account_id"],
                    "event_timestamp": (start + timedelta(minutes=i * 11)).isoformat(),
                    "risk_score": score,
                    "risk_category": category,
                    "risk_status": status,
                    "risk_reason": RISK_REASONS[i % len(RISK_REASONS)],
                    "exposure_amount": str(exposure.quantize(Decimal("0.01"))),
                })

        if need("trades"):
            data["trades"] = []
            active_accounts = [row for row in data["accounts"] if row["account_status"] == "Active"]
            risk_events = data.get("risk_events", [])
            for i in range(1, trade_count + 1):
                account = active_accounts[i % len(active_accounts)]
                symbol = INSTRUMENT_SYMBOLS[i % len(INSTRUMENT_SYMBOLS)]
                quantity = Decimal(1 + (i % 750))
                price = Decimal(20 + (i % 350)) + Decimal(self.rng.randrange(0, 100)) / 100
                notional = (quantity * price).quantize(Decimal("0.01"))
                status = "Executed" if i % 17 else TRADE_STATUSES[i % len(TRADE_STATUSES)]
                risk_event_id = risk_events[i % len(risk_events)]["risk_event_id"] if risk_events and i % 37 == 0 else None
                data["trades"].append({
                    "trade_id": 8100000 + i,
                    "account_id": account["account_id"],
                    "instrument_symbol": symbol,
                    "trade_side": TRADE_SIDES[i % len(TRADE_SIDES)],
                    "quantity": str(quantity),
                    "price": str(price.quantize(Decimal("0.01"))),
                    "notional_amount": str(notional),
                    "trade_timestamp": (start + timedelta(seconds=i * 13)).isoformat(),
                    "trade_status": status,
                    "rejection_reason": RISK_REASONS[i % len(RISK_REASONS)] if status == "Rejected" else "not_applicable",
                    "risk_event_id": risk_event_id,
                })

        if need("market_data"):
            data["market_data"] = []
            risk_events = data.get("risk_events", [])
            for i in range(1, market_data_count + 1):
                symbol = INSTRUMENT_SYMBOLS[i % len(INSTRUMENT_SYMBOLS)]
                price = Decimal(20 + (i % 350)) + Decimal(self.rng.randrange(0, 100)) / 100
                spread = Decimal("0.05") + Decimal(i % 20) / Decimal("100")
                status = "Open" if i % 23 else MARKET_STATUSES[i % len(MARKET_STATUSES)]
                risk_event_id = risk_events[i % len(risk_events)]["risk_event_id"] if risk_events and status == "Halted" else None
                data["market_data"].append({
                    "market_data_id": 9100000 + i,
                    "instrument_symbol": symbol,
                    "quote_timestamp": (start + timedelta(seconds=i * 5)).isoformat(),
                    "price": str(price.quantize(Decimal("0.01"))),
                    "bid_price": str((price - spread).quantize(Decimal("0.01"))),
                    "ask_price": str((price + spread).quantize(Decimal("0.01"))),
                    "market_status": status,
                    "market_event_reason": RISK_REASONS[i % len(RISK_REASONS)] if status == "Halted" else "not_applicable",
                    "risk_event_id": risk_event_id,
                })

        if need("positions"):
            data["positions"] = []
            active_accounts = [row for row in data["accounts"] if row["account_status"] == "Active"]
            risk_events = data.get("risk_events", [])
            for i in range(1, position_count + 1):
                account = active_accounts[i % len(active_accounts)]
                symbol = INSTRUMENT_SYMBOLS[i % len(INSTRUMENT_SYMBOLS)]
                quantity = Decimal(1 + (i % 1000))
                average_cost = Decimal(15 + (i % 300)) + Decimal(self.rng.randrange(0, 100)) / 100
                market_value = (quantity * average_cost * Decimal("1.03")).quantize(Decimal("0.01"))
                status = "Open" if i % 29 else POSITION_STATUSES[i % len(POSITION_STATUSES)]
                risk_event_id = risk_events[i % len(risk_events)]["risk_event_id"] if risk_events and i % 41 == 0 else None
                data["positions"].append({
                    "position_id": 10100000 + i,
                    "account_id": account["account_id"],
                    "instrument_symbol": symbol,
                    "quantity": str(quantity),
                    "average_cost": str(average_cost.quantize(Decimal("0.01"))),
                    "market_value": str(market_value),
                    "position_date": (start + timedelta(minutes=i * 19)).isoformat(),
                    "position_status": status,
                    "position_reason": RISK_REASONS[i % len(RISK_REASONS)] if status in {"Closed", "Restricted"} else "not_applicable",
                    "risk_event_id": risk_event_id,
                })

        return enrich_dataset(data, self.load_type, self.scd_type, FINANCE_SPEC)
