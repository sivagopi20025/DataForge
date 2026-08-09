from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from ...audit import enrich_dataset
from ...model import Dataset
from ...synthetic_values import full_name, unique_email
from .constants import (
    CALL_STATUSES,
    CALL_TYPES,
    CITIES,
    COVERAGE_TYPES,
    CUSTOMER_STATUSES,
    CUSTOMER_TYPES,
    DELIVERY_STATUSES,
    DEVICE_MANUFACTURERS,
    DEVICE_TYPES,
    FIRST_NAMES,
    INVOICE_STATUSES,
    LAST_NAMES,
    MESSAGE_TYPES,
    NETWORK_EVENT_STATUSES,
    NETWORK_EVENT_TYPES,
    NETWORK_TYPES,
    OS_TYPES,
    PAYMENT_METHODS,
    PAYMENT_STATUSES,
    PLAN_TYPES,
    SEVERITIES,
    SESSION_STATUSES,
    SIM_STATUSES,
    SUBSCRIPTION_STATUSES,
    SUBSCRIPTION_TYPES,
    TECHNOLOGIES,
    TICKET_PRIORITIES,
    TICKET_STATUSES,
    TICKET_TYPES,
    TOWER_TYPES,
)
from .schemas import TELECOMMUNICATIONS_SPEC


class TelecommunicationsGenerator:
    def __init__(self, cdr_records: int, seed: int = 42, load_type: str = "bulk", scd_type: int = 1) -> None:
        if cdr_records < 1:
            raise ValueError("records must be at least 1")
        self.cdr_records = cdr_records
        self.rng = random.Random(seed)
        self.load_type = load_type
        self.scd_type = scd_type
        self.today = date(2026, 6, 22)
        self.selected_tables: set[str] | None = None

    def _count(self, ratio: float, minimum: int, maximum: int | None = None) -> int:
        value = max(minimum, int(self.cdr_records * ratio))
        return min(value, maximum) if maximum else value

    def _money(self, value: Decimal) -> str:
        return str(value.quantize(Decimal("0.01")))

    def _phone(self, index: int) -> str:
        return f"+1555{index:07d}"[-12:]

    def generate(self) -> Dataset:
        selected = self.selected_tables
        full = not selected
        required = set(TELECOMMUNICATIONS_SPEC.schemas) if full else set(selected)
        dependencies = {
            "subscriptions": {"telecom_customers", "plans"},
            "sim_cards": {"subscriptions"},
            "devices": {"subscriptions"},
            "cell_towers": {"network_regions"},
            "call_detail_records": {"subscriptions", "sim_cards", "devices", "cell_towers"},
            "sms_records": {"subscriptions", "sim_cards", "devices", "cell_towers"},
            "data_sessions": {"subscriptions", "sim_cards", "devices", "cell_towers"},
            "billing_accounts": {"telecom_customers"},
            "invoices": {"billing_accounts"},
            "payments": {"invoices"},
            "network_events": {"cell_towers"},
            "support_tickets": {"telecom_customers", "subscriptions"},
        }
        changed = True
        while changed:
            changed = False
            for table in tuple(required):
                missing = dependencies.get(table, set()) - required
                if missing:
                    required.update(missing)
                    changed = True

        def need(table: str) -> bool:
            return table in required

        need_customers = need("telecom_customers")
        need_plans = need("plans")
        need_subscriptions = need("subscriptions")
        need_sims = need("sim_cards")
        need_devices = need("devices")
        need_regions = need("network_regions")
        need_towers = need("cell_towers")
        need_billing = need("billing_accounts")
        need_invoices = need("invoices")

        customer_count = self._count(0.20, 100, 100000)
        plan_count = self._count(0.01, 12, 500)
        subscription_count = self._count(0.30, 150, 150000)
        region_count = self._count(0.02, 8, 2500)
        tower_count = self._count(0.08, 25, 20000)
        billing_count = customer_count
        invoice_count = self._count(0.25, 80, 150000)
        payment_count = self._count(0.20, 60, 150000)
        sms_count = max(1, int(self.cdr_records * 0.8))
        data_session_count = max(1, int(self.cdr_records * 0.9))
        network_event_count = self._count(0.03, 5, 10000)
        ticket_count = self._count(0.06, 10, 30000)
        start = datetime(2026, 6, 21) if self.load_type in {"incremental", "delta", "cdc", "event", "event_stream"} else datetime(2026, 1, 1)
        data: Dataset = {}

        if need_customers:
            data["telecom_customers"] = []
            for i in range(1, customer_count + 1):
                city, state, country = CITIES[i % len(CITIES)]
                name = full_name(i, "telecommunications")
                data["telecom_customers"].append({
                    "customer_id": 1000000 + i,
                    "customer_name": name,
                    "customer_type": CUSTOMER_TYPES[i % len(CUSTOMER_TYPES)],
                    "email": unique_email(*name.split(" ", 1), 1000000 + i, "telecom.customer"),
                    "phone_number": self._phone(i),
                    "country": country,
                    "state": state,
                    "city": city,
                    "registration_date": str(self.today - timedelta(days=30 + i % 3000)),
                    "status": "active" if i % 31 else CUSTOMER_STATUSES[i % len(CUSTOMER_STATUSES)],
                    "created_at": str(self.today - timedelta(days=30 + i % 3000)),
                })

        if need_plans:
            data["plans"] = []
            for i in range(1, plan_count + 1):
                plan_type = PLAN_TYPES[i % len(PLAN_TYPES)]
                monthly = Decimal(15 + (i % 120)) + Decimal(self.rng.randrange(0, 100)) / 100
                data["plans"].append({
                    "plan_id": 2000000 + i,
                    "plan_name": f"{plan_type.replace('_', ' ').title()} Plan {i:03d}",
                    "plan_type": plan_type,
                    "monthly_fee": self._money(monthly),
                    "voice_minutes_included": 500 + i % 5000,
                    "sms_included": 500 + i % 10000,
                    "data_gb_included": 5 + i % 200,
                    "roaming_enabled": i % 3 == 0,
                    "active_flag": i % 29 != 0,
                    "created_at": str(self.today - timedelta(days=200 + i % 900)),
                })

        if need_subscriptions:
            data["subscriptions"] = []
            for i in range(1, subscription_count + 1):
                customer = data["telecom_customers"][(i - 1) % len(data["telecom_customers"])]
                plan = data["plans"][(i - 1) % len(data["plans"])]
                start_date = self.today - timedelta(days=10 + i % 2000)
                data["subscriptions"].append({
                    "subscription_id": 3000000 + i,
                    "customer_id": customer["customer_id"],
                    "plan_id": plan["plan_id"],
                    "subscription_type": SUBSCRIPTION_TYPES[i % len(SUBSCRIPTION_TYPES)],
                    "start_date": str(start_date),
                    "end_date": str(start_date + timedelta(days=365 + i % 720)),
                    "status": "active" if i % 23 else SUBSCRIPTION_STATUSES[i % len(SUBSCRIPTION_STATUSES)],
                    "billing_cycle": ("monthly", "quarterly", "annual")[i % 3],
                    "created_at": str(start_date),
                })

        if need_sims:
            data["sim_cards"] = []
            for i, subscription in enumerate(data["subscriptions"], 1):
                data["sim_cards"].append({
                    "sim_id": 4000000 + i,
                    "subscription_id": subscription["subscription_id"],
                    "iccid": f"8901410321111851{i:06d}",
                    "imsi": f"310150{i:09d}",
                    "phone_number": self._phone(i),
                    "activation_date": subscription["start_date"],
                    "status": "active" if i % 37 else SIM_STATUSES[i % len(SIM_STATUSES)],
                    "created_at": subscription["start_date"],
                })

        if need_devices:
            data["devices"] = []
            for i, subscription in enumerate(data["subscriptions"], 1):
                device_type = DEVICE_TYPES[i % len(DEVICE_TYPES)]
                data["devices"].append({
                    "device_id": 5000000 + i,
                    "subscription_id": subscription["subscription_id"],
                    "imei": f"35{i:013d}"[-15:],
                    "device_type": device_type,
                    "manufacturer": DEVICE_MANUFACTURERS[i % len(DEVICE_MANUFACTURERS)],
                    "model": f"{device_type.replace('_', ' ').title()}-{i % 1000:03d}",
                    "os_type": OS_TYPES[i % len(OS_TYPES)],
                    "purchase_date": subscription["start_date"],
                    "status": "active" if i % 41 else "inactive",
                    "created_at": subscription["start_date"],
                })

        if need_regions:
            data["network_regions"] = []
            for i in range(1, region_count + 1):
                city, state, country = CITIES[i % len(CITIES)]
                data["network_regions"].append({
                    "region_id": 6000000 + i,
                    "region_name": f"{city} Region {i:04d}",
                    "country": country,
                    "state": state,
                    "city": city,
                    "coverage_type": COVERAGE_TYPES[i % len(COVERAGE_TYPES)],
                    "created_at": str(self.today - timedelta(days=250 + i % 1000)),
                })

        if need_towers:
            data["cell_towers"] = []
            for i in range(1, tower_count + 1):
                region = data["network_regions"][(i - 1) % len(data["network_regions"])]
                data["cell_towers"].append({
                    "tower_id": 7000000 + i,
                    "region_id": region["region_id"],
                    "tower_code": f"TWR-{region['region_id']}-{i:05d}",
                    "latitude": round(25.0 + (i % 2200) / 100, 6),
                    "longitude": round(-125.0 + (i % 6000) / 100, 6),
                    "tower_type": TOWER_TYPES[i % len(TOWER_TYPES)],
                    "technology": TECHNOLOGIES[i % len(TECHNOLOGIES)],
                    "status": "active" if i % 43 else "maintenance",
                    "installed_date": str(self.today - timedelta(days=300 + i % 3000)),
                    "created_at": str(self.today - timedelta(days=300 + i % 3000)),
                })

        if need("call_detail_records"):
            data["call_detail_records"] = []
            for i in range(1, self.cdr_records + 1):
                subscription = data["subscriptions"][(i - 1) % len(data["subscriptions"])]
                sim = data["sim_cards"][(i - 1) % len(data["sim_cards"])]
                device = data["devices"][(i - 1) % len(data["devices"])]
                tower = data["cell_towers"][(i - 1) % len(data["cell_towers"])]
                call_start = start + timedelta(seconds=i * 17)
                duration = 15 + (i % 3600)
                data["call_detail_records"].append({
                    "cdr_id": 8000000 + i,
                    "subscription_id": subscription["subscription_id"],
                    "sim_id": sim["sim_id"],
                    "device_id": device["device_id"],
                    "tower_id": tower["tower_id"],
                    "caller_number": sim["phone_number"],
                    "receiver_number": self._phone(i + 900000),
                    "call_start_time": call_start.isoformat(),
                    "call_end_time": (call_start + timedelta(seconds=duration)).isoformat(),
                    "duration_seconds": duration,
                    "call_type": CALL_TYPES[i % len(CALL_TYPES)],
                    "call_status": "completed" if i % 19 else CALL_STATUSES[i % len(CALL_STATUSES)],
                    "cost": self._money(Decimal(duration) * Decimal("0.002")),
                    "created_at": call_start.date().isoformat(),
                })

        if need("sms_records"):
            data["sms_records"] = []
            for i in range(1, sms_count + 1):
                sim = data["sim_cards"][(i - 1) % len(data["sim_cards"])]
                device = data["devices"][(i - 1) % len(data["devices"])]
                tower = data["cell_towers"][(i - 1) % len(data["cell_towers"])]
                sent = start + timedelta(seconds=i * 23)
                data["sms_records"].append({
                    "sms_id": 9000000 + i,
                    "subscription_id": sim["subscription_id"],
                    "sim_id": sim["sim_id"],
                    "device_id": device["device_id"],
                    "tower_id": tower["tower_id"],
                    "sender_number": sim["phone_number"],
                    "receiver_number": self._phone(i + 700000),
                    "sent_time": sent.isoformat(),
                    "delivery_status": "delivered" if i % 17 else DELIVERY_STATUSES[i % len(DELIVERY_STATUSES)],
                    "message_type": MESSAGE_TYPES[i % len(MESSAGE_TYPES)],
                    "cost": self._money(Decimal("0.01") if i % 5 else Decimal("0.00")),
                    "created_at": sent.date().isoformat(),
                })

        if need("data_sessions"):
            data["data_sessions"] = []
            for i in range(1, data_session_count + 1):
                sim = data["sim_cards"][(i - 1) % len(data["sim_cards"])]
                device = data["devices"][(i - 1) % len(data["devices"])]
                tower = data["cell_towers"][(i - 1) % len(data["cell_towers"])]
                session_start = start + timedelta(seconds=i * 31)
                duration_minutes = 1 + i % 240
                used_mb = Decimal(1 + i % 5000) + Decimal(self.rng.randrange(0, 100)) / 100
                data["data_sessions"].append({
                    "session_id": 10000000 + i,
                    "subscription_id": sim["subscription_id"],
                    "sim_id": sim["sim_id"],
                    "device_id": device["device_id"],
                    "tower_id": tower["tower_id"],
                    "session_start_time": session_start.isoformat(),
                    "session_end_time": (session_start + timedelta(minutes=duration_minutes)).isoformat(),
                    "data_used_mb": self._money(used_mb),
                    "network_type": NETWORK_TYPES[i % len(NETWORK_TYPES)],
                    "session_status": "completed" if i % 23 else SESSION_STATUSES[i % len(SESSION_STATUSES)],
                    "cost": self._money(used_mb * Decimal("0.005")),
                    "created_at": session_start.date().isoformat(),
                })

        if need_billing:
            data["billing_accounts"] = []
            for i in range(1, billing_count + 1):
                customer = data["telecom_customers"][(i - 1) % len(data["telecom_customers"])]
                data["billing_accounts"].append({
                    "billing_account_id": 11000000 + i,
                    "customer_id": customer["customer_id"],
                    "account_number": f"BA-{i:010d}",
                    "billing_address": f"{100 + i % 9000} {customer['city']} Telecom Way",
                    "billing_email": customer["email"],
                    "payment_method": PAYMENT_METHODS[i % len(PAYMENT_METHODS)],
                    "status": "active" if i % 29 else "past_due",
                    "created_at": customer["registration_date"],
                })

        if need_invoices:
            data["invoices"] = []
            for i in range(1, invoice_count + 1):
                account = data["billing_accounts"][(i - 1) % len(data["billing_accounts"])]
                voice = Decimal(i % 80) + Decimal("2.50")
                sms = Decimal(i % 25) * Decimal("0.10")
                data_charge = Decimal(i % 150) + Decimal("5.00")
                taxes = (voice + sms + data_charge) * Decimal("0.085")
                total = voice + sms + data_charge + taxes
                due = start.date() + timedelta(days=15 + i % 30)
                data["invoices"].append({
                    "invoice_id": 12000000 + i,
                    "billing_account_id": account["billing_account_id"],
                    "invoice_month": f"2026-{1 + i % 12:02d}",
                    "total_voice_charges": self._money(voice),
                    "total_sms_charges": self._money(sms),
                    "total_data_charges": self._money(data_charge),
                    "taxes": self._money(taxes),
                    "total_amount": self._money(total),
                    "due_date": due.isoformat(),
                    "status": "paid" if i % 5 else INVOICE_STATUSES[i % len(INVOICE_STATUSES)],
                    "created_at": (due - timedelta(days=15)).isoformat(),
                })

        if need("payments"):
            data["payments"] = []
            for i in range(1, payment_count + 1):
                invoice = data["invoices"][(i - 1) % len(data["invoices"])]
                data["payments"].append({
                    "payment_id": 13000000 + i,
                    "invoice_id": invoice["invoice_id"],
                    "payment_date": (date.fromisoformat(invoice["due_date"]) - timedelta(days=i % 10)).isoformat(),
                    "payment_method": PAYMENT_METHODS[i % len(PAYMENT_METHODS)],
                    "payment_amount": invoice["total_amount"] if i % 13 else self._money(Decimal(invoice["total_amount"]) / Decimal("2")),
                    "payment_status": "successful" if i % 17 else PAYMENT_STATUSES[i % len(PAYMENT_STATUSES)],
                    "transaction_reference": f"TELPAY-{i:012d}",
                    "created_at": invoice["created_at"],
                })

        if need("network_events"):
            data["network_events"] = []
            for i in range(1, network_event_count + 1):
                tower = data["cell_towers"][(i - 1) % len(data["cell_towers"])]
                event_start = start + timedelta(minutes=i * 11)
                duration = 10 + i % 360
                data["network_events"].append({
                    "network_event_id": 14000000 + i,
                    "tower_id": tower["tower_id"],
                    "region_id": tower["region_id"],
                    "event_type": NETWORK_EVENT_TYPES[i % len(NETWORK_EVENT_TYPES)],
                    "severity": SEVERITIES[i % len(SEVERITIES)],
                    "event_start_time": event_start.isoformat(),
                    "event_end_time": (event_start + timedelta(minutes=duration)).isoformat(),
                    "affected_users": i % 50000,
                    "root_cause": ("power", "capacity", "hardware", "software", "weather")[i % 5],
                    "status": "resolved" if i % 3 else NETWORK_EVENT_STATUSES[i % len(NETWORK_EVENT_STATUSES)],
                    "created_at": event_start.date().isoformat(),
                })

        if need("support_tickets"):
            data["support_tickets"] = []
            for i in range(1, ticket_count + 1):
                customer = data["telecom_customers"][(i - 1) % len(data["telecom_customers"])]
                subscription = data["subscriptions"][(i - 1) % len(data["subscriptions"])]
                opened = start + timedelta(minutes=i * 19)
                data["support_tickets"].append({
                    "ticket_id": 15000000 + i,
                    "customer_id": customer["customer_id"],
                    "subscription_id": subscription["subscription_id"],
                    "ticket_type": TICKET_TYPES[i % len(TICKET_TYPES)],
                    "priority": TICKET_PRIORITIES[i % len(TICKET_PRIORITIES)],
                    "status": "resolved" if i % 4 else TICKET_STATUSES[i % len(TICKET_STATUSES)],
                    "opened_at": opened.isoformat(),
                    "resolved_at": (opened + timedelta(hours=1 + i % 96)).isoformat(),
                    "resolution_summary": f"Ticket {i:06d} handled by support workflow",
                    "created_at": opened.date().isoformat(),
                })

        return enrich_dataset(data, self.load_type, self.scd_type, TELECOMMUNICATIONS_SPEC)
