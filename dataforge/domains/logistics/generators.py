from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from ...audit import enrich_dataset
from ...model import Dataset
from ...synthetic_values import full_name, unique_email
from .schemas import LOGISTICS_SPEC


CITIES = (
    ("Atlanta", "GA", 33.7490, -84.3880),
    ("Austin", "TX", 30.2672, -97.7431),
    ("Chicago", "IL", 41.8781, -87.6298),
    ("Denver", "CO", 39.7392, -104.9903),
    ("Seattle", "WA", 47.6062, -122.3321),
)
NAMES = ("Ava Patel", "Liam Smith", "Mia Chen", "Noah Garcia", "Emma Brown", "Ethan Wilson", "Zoe Kim", "Lucas Davis")


class LogisticsGenerator:
    def __init__(self, shipment_records: int, seed: int = 42, load_type: str = "bulk", scd_type: int = 1) -> None:
        if shipment_records < 1:
            raise ValueError("records must be at least 1")
        self.shipment_records = shipment_records
        self.rng = random.Random(seed)
        self.load_type = load_type
        self.scd_type = scd_type
        self.today = date(2026, 6, 22)
        self.selected_tables: set[str] | None = None

    def _count(self, ratio: float, minimum: int, maximum: int | None = None) -> int:
        value = max(minimum, int(self.shipment_records * ratio))
        return min(value, maximum) if maximum else value

    def generate(self) -> Dataset:
        selected = self.selected_tables
        full = not selected

        def need(table: str) -> bool:
            return full or table in selected

        need_shipments = full or bool(selected & {"shipments", "delivery_records", "tracking_events", "exception_alerts"})
        need_customers = full or bool(selected & {"customers", "shipments", "delivery_records", "tracking_events", "exception_alerts"})
        need_warehouses = full or bool(selected & {"warehouses", "shipments", "delivery_records", "tracking_events", "exception_alerts"})
        need_drivers = full or bool(selected & {"drivers", "vehicles", "delivery_records", "gps_events"})
        need_vehicles = full or bool(selected & {"vehicles", "gps_events"})
        counts = {
            "customers": min(50000, self._count(0.08, 50)),
            "warehouses": min(250, self._count(0.002, 5)),
            "drivers": min(10000, self._count(0.03, 25)),
            "vehicles": min(10000, self._count(0.03, 25)),
        }
        data: Dataset = {}
        if need_customers:
            data["customers"] = []
            for i in range(1, counts["customers"] + 1):
                city, state, _, _ = CITIES[i % len(CITIES)]
                data["customers"].append({
                    "customer_id": 900000 + i,
                    "customer_name": f"Logistics Customer {i:06d}",
                    "customer_type": ("retail", "enterprise", "marketplace")[i % 3],
                    "email": unique_email("logistics", "customer", 900000 + i, "logistics.customer"),
                    "phone": f"555-{i % 1000:03d}-{(i * 19) % 10000:04d}",
                    "country": "USA",
                    "state": state,
                    "city": city,
                    "postal_code": f"{30000 + (i % 60000):05d}",
                    "created_at": str(self.today - timedelta(days=i % 1500)),
                })
        if need_warehouses:
            data["warehouses"] = []
            for i in range(1, counts["warehouses"] + 1):
                city, state, lat, lon = CITIES[(i - 1) % len(CITIES)]
                data["warehouses"].append({
                    "warehouse_id": 7000 + i,
                    "warehouse_name": f"Warehouse {city} {i:03d}",
                    "country": "USA",
                    "state": state,
                    "city": city,
                    "postal_code": f"{31000 + i:05d}",
                    "capacity": 50000 + i * 1500,
                    "latitude": round(lat + self.rng.uniform(-0.08, 0.08), 6),
                    "longitude": round(lon + self.rng.uniform(-0.08, 0.08), 6),
                })
        if need_drivers:
            data["drivers"] = []
            for i in range(1, counts["drivers"] + 1):
                data["drivers"].append({
                    "driver_id": 800000 + i,
                    "driver_name": full_name(i, "logistics.driver"),
                    "license_number": f"DL-{i:09d}",
                    "phone": f"555-{(i * 3) % 1000:03d}-{(i * 23) % 10000:04d}",
                    "status": ("available", "assigned", "off_duty")[i % 3],
                    "hire_date": str(self.today - timedelta(days=90 + i % 2600)),
                })
        if need_vehicles:
            data["vehicles"] = []
            for i in range(1, counts["vehicles"] + 1):
                data["vehicles"].append({
                    "vehicle_id": 600000 + i,
                    "vehicle_number": f"TRK-{i:06d}",
                    "vehicle_type": ("van", "box_truck", "tractor_trailer")[i % 3],
                    "capacity_kg": (1200, 5000, 18000)[i % 3],
                    "driver_id": data["drivers"][(i - 1) % len(data["drivers"])]["driver_id"],
                    "status": ("active", "maintenance", "active")[i % 3],
                })
        start = datetime(2026, 6, 21) if self.load_type in {"incremental", "delta", "cdc", "event", "event_stream"} else datetime(2026, 1, 1)
        status_flow = ("created", "packed", "in_transit", "delivered")
        if need_shipments:
            data["shipments"] = []
            for i in range(1, self.shipment_records + 1):
                source = data["warehouses"][i % len(data["warehouses"])]
                destination = data["warehouses"][(i + 2) % len(data["warehouses"])]
                created_at = start + timedelta(minutes=i * 3)
                data["shipments"].append({
                    "shipment_id": 5000000 + i,
                    "customer_id": data["customers"][self.rng.randrange(len(data["customers"]))]["customer_id"],
                    "source_warehouse_id": source["warehouse_id"],
                    "destination_warehouse_id": destination["warehouse_id"],
                    "shipment_type": ("standard", "express", "cold_chain", "fragile")[i % 4],
                    "weight_kg": round(self.rng.uniform(1.0, 2500.0), 2),
                    "volume_cbm": round(self.rng.uniform(0.1, 35.0), 2),
                    "shipment_status": status_flow[i % len(status_flow)],
                    "created_at": created_at.isoformat(),
                })
        if need("delivery_records"):
            data["delivery_records"] = []
            delivered = [row for row in data["shipments"] if row["shipment_status"] == "delivered"]
            for i, shipment in enumerate(delivered, 1):
                driver = data["drivers"][i % len(data["drivers"])]
                delivered_at = datetime.fromisoformat(shipment["created_at"]) + timedelta(hours=18 + i % 72)
                data["delivery_records"].append({
                    "delivery_id": 4000000 + i,
                    "shipment_id": shipment["shipment_id"],
                    "driver_id": driver["driver_id"],
                    "delivery_date": delivered_at.isoformat(),
                    "delivery_status": "delivered",
                    "delivery_time_minutes": 60 * (18 + i % 72),
                })
        if need("tracking_events") or need("exception_alerts"):
            data["tracking_events"] = []
            event_id = 1
            for shipment in data["shipments"]:
                shipment_time = datetime.fromisoformat(shipment["created_at"])
                events = ["created", "packed", "in_transit"]
                if shipment["shipment_status"] == "delivered":
                    events.append("delivered")
                for offset, event_type in enumerate(events):
                    data["tracking_events"].append({
                        "event_id": 3000000 + event_id,
                        "shipment_id": shipment["shipment_id"],
                        "event_type": event_type,
                        "event_timestamp": (shipment_time + timedelta(hours=offset * 6)).isoformat(),
                        "location": CITIES[(shipment["shipment_id"] + offset) % len(CITIES)][0],
                    })
                    event_id += 1
        if need("exception_alerts"):
            data["exception_alerts"] = []
            alert_count = min(len(data["shipments"]), max(1, int(self.shipment_records * 0.12)))
            alert_profiles = (
                ("delay", "carrier_delay", "medium", 125.00),
                ("temperature_breach", "temperature_excursion", "critical", 750.00),
                ("address_issue", "invalid_address", "low", 45.00),
                ("customs_hold", "customs_documentation", "high", 425.00),
                ("damage", "package_damage", "high", 350.00),
                ("lost_scan", "tracking_gap", "medium", 90.00),
            )
            events_by_shipment: dict[int, list[dict]] = {}
            for event in data.get("tracking_events", []):
                events_by_shipment.setdefault(event["shipment_id"], []).append(event)
            for i in range(1, alert_count + 1):
                shipment = data["shipments"][(i * 7 - 1) % len(data["shipments"])]
                alert_type, reason_code, severity, base_cost = alert_profiles[i % len(alert_profiles)]
                source_events = events_by_shipment.get(shipment["shipment_id"], [])
                source_event = source_events[min(len(source_events) - 1, 1)] if source_events else None
                anchor_time = datetime.fromisoformat(source_event["event_timestamp"]) if source_event else datetime.fromisoformat(shipment["created_at"])
                alert_timestamp = anchor_time + timedelta(hours=1 + i % 12)
                status = "resolved" if i % 5 else ("acknowledged" if i % 2 else "open")
                resolved_at = alert_timestamp + timedelta(hours=2 + i % 36)
                data["exception_alerts"].append({
                    "exception_alert_id": 9000000 + i,
                    "shipment_id": shipment["shipment_id"],
                    "source_event_id": source_event["event_id"] if source_event else "",
                    "alert_type": alert_type,
                    "alert_timestamp": alert_timestamp.isoformat(),
                    "severity": severity,
                    "status": status,
                    "exception_reason": reason_code.replace("_", " "),
                    "reason_code": reason_code,
                    "estimated_impact_cost": round(base_cost + (i % 250) * 1.75, 2),
                    "resolved_at": resolved_at.isoformat() if status == "resolved" else "not_applicable",
                    "created_at": alert_timestamp.isoformat(),
                })
        if need("gps_events"):
            data["gps_events"] = []
            gps_count = max(self.shipment_records, self._count(1.5, 25))
            for i in range(1, gps_count + 1):
                vehicle = data["vehicles"][i % len(data["vehicles"])]
                city = CITIES[i % len(CITIES)]
                data["gps_events"].append({
                    "event_id": 2000000 + i,
                    "vehicle_id": vehicle["vehicle_id"],
                    "latitude": round(city[2] + self.rng.uniform(-0.15, 0.15), 6),
                    "longitude": round(city[3] + self.rng.uniform(-0.15, 0.15), 6),
                    "speed": round(max(0.0, self.rng.gauss(48, 18)), 2),
                    "timestamp": (start + timedelta(minutes=i)).isoformat(),
                })
        return enrich_dataset(data, self.load_type, self.scd_type, LOGISTICS_SPEC)
