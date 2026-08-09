from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from ...audit import enrich_dataset, record_hash
from ...model import Dataset
from ...synthetic_values import full_name
from .constants import (
    BATCH_STATUSES,
    CITIES,
    DEFECT_TYPES,
    EMPLOYEE_ROLES,
    FACTORY_STATUSES,
    FACTORY_TYPES,
    FIRST_NAMES,
    INVENTORY_TYPES,
    LAST_NAMES,
    LINE_STATUSES,
    MACHINE_STATUSES,
    MACHINE_TYPES,
    MAINTENANCE_PRIORITIES,
    MAINTENANCE_STATUSES,
    MAINTENANCE_TYPES,
    MANUFACTURERS,
    MATERIAL_TYPES,
    PRODUCT_CATEGORIES,
    QUALITY_CHECK_TYPES,
    QUALITY_RESULTS,
    ROOT_CAUSES,
    SEVERITIES,
    SHIFTS,
    SUPPLIER_STATUSES,
    UNITS_OF_MEASURE,
    WORK_ORDER_STATUSES,
)
from .schemas import MANUFACTURING_SPEC


class ManufacturingGenerator:
    def __init__(self, work_order_records: int, seed: int = 42, load_type: str = "bulk", scd_type: int = 1) -> None:
        if work_order_records < 1:
            raise ValueError("records must be at least 1")
        self.work_order_records = work_order_records
        self.rng = random.Random(seed)
        self.load_type = load_type
        self.scd_type = scd_type
        self.today = date(2026, 6, 22)
        self.selected_tables: set[str] | None = None

    def _count(self, ratio: float, minimum: int, maximum: int | None = None) -> int:
        value = max(minimum, int(self.work_order_records * ratio))
        return min(value, maximum) if maximum else value

    def _money(self, value: Decimal) -> str:
        return str(value.quantize(Decimal("0.01")))

    def generate(self) -> Dataset:
        selected = self.selected_tables
        full = not selected

        def need(table: str) -> bool:
            return full or table in selected

        need_factories = full or bool(selected & {"factories", "production_lines", "machines", "employees", "inventory", "work_orders", "sensor_readings"})
        need_lines = full or bool(selected & {"production_lines", "machines", "work_orders", "production_batches", "sensor_readings"})
        need_machines = full or bool(selected & {"machines", "maintenance_orders", "sensor_readings"})
        need_products = full or bool(selected & {"products", "work_orders", "production_batches", "inventory"})
        need_suppliers = full or bool(selected & {"suppliers", "raw_materials"})
        need_materials = full or bool(selected & {"raw_materials", "inventory"})
        need_employees = full or bool(selected & {"employees", "quality_checks", "maintenance_orders"})
        need_work_orders = full or bool(selected & {"work_orders", "production_batches"})
        need_batches = full or bool(selected & {"production_batches", "quality_checks", "defects"})
        need_quality = full or bool(selected & {"quality_checks", "defects"})

        factory_count = self._count(0.01, 5, 200)
        line_count = self._count(0.03, 10, 1000)
        machine_count = self._count(0.08, 25, 5000)
        product_count = self._count(0.04, 20, 5000)
        supplier_count = self._count(0.02, 10, 2000)
        material_count = self._count(0.06, 30, 10000)
        employee_count = self._count(0.10, 40, 20000)
        batch_count = max(1, int(self.work_order_records * 1.2))
        quality_count = batch_count
        defect_count = max(1, int(batch_count * 0.18))
        maintenance_count = max(1, int(machine_count * 0.25))
        sensor_count = max(1, int(self.work_order_records * 1.5))
        inventory_count = material_count + product_count
        start = datetime(2026, 6, 21) if self.load_type in {"incremental", "delta", "cdc", "event", "event_stream"} else datetime(2026, 1, 1)
        data: Dataset = {}

        if need_factories:
            data["factories"] = []
            for i in range(1, factory_count + 1):
                city, state, country = CITIES[i % len(CITIES)]
                data["factories"].append({
                    "factory_id": 100000 + i,
                    "factory_name": f"{city} Manufacturing Plant {i:04d}",
                    "country": country,
                    "state": state,
                    "city": city,
                    "factory_type": FACTORY_TYPES[i % len(FACTORY_TYPES)],
                    "planned_capacity_amount": 10000 + (i % 500) * 125,
                    "opened_date": str(self.today - timedelta(days=365 + i * 17)),
                    "status": "active" if i % 23 else FACTORY_STATUSES[i % len(FACTORY_STATUSES)],
                    "created_at": str(self.today - timedelta(days=300 + i % 1000)),
                })

        if need_lines:
            data["production_lines"] = []
            for i in range(1, line_count + 1):
                factory = data["factories"][(i - 1) % len(data["factories"])]
                data["production_lines"].append({
                    "line_id": 200000 + i,
                    "factory_id": factory["factory_id"],
                    "line_name": f"Line-{factory['factory_id']}-{i:04d}",
                    "product_category": PRODUCT_CATEGORIES[i % len(PRODUCT_CATEGORIES)],
                    "capacity_per_hour": 50 + (i % 450),
                    "shift_count": 1 + (i % 3),
                    "status": "active" if i % 19 else LINE_STATUSES[i % len(LINE_STATUSES)],
                    "risk_score": round(0.10 + ((i % 17) / 100), 3),
                    "idempotency_key": f"MFG-LINE-{200000 + i}",
                    "created_at": str(self.today - timedelta(days=120 + i % 700)),
                })

        if need_machines:
            data["machines"] = []
            for i in range(1, machine_count + 1):
                line = data["production_lines"][(i - 1) % len(data["production_lines"])]
                data["machines"].append({
                    "machine_id": 300000 + i,
                    "line_id": line["line_id"],
                    "machine_name": f"{MACHINE_TYPES[i % len(MACHINE_TYPES)]}-{i:06d}",
                    "machine_type": MACHINE_TYPES[i % len(MACHINE_TYPES)],
                    "manufacturer": MANUFACTURERS[i % len(MANUFACTURERS)],
                    "install_date": str(self.today - timedelta(days=90 + i % 2500)),
                    "expected_life_years": 5 + (i % 15),
                    "status": "active" if i % 31 else MACHINE_STATUSES[i % len(MACHINE_STATUSES)],
                    "created_at": str(self.today - timedelta(days=90 + i % 2500)),
                })

        if need("sensor_readings"):
            data["sensor_readings"] = []
            sensor_profiles = (
                ("temperature", "celsius", Decimal("55.0"), Decimal("28.0")),
                ("vibration", "mm_s", Decimal("2.5"), Decimal("7.5")),
                ("pressure", "psi", Decimal("80.0"), Decimal("60.0")),
                ("current", "ampere", Decimal("12.0"), Decimal("18.0")),
            )
            for i in range(1, sensor_count + 1):
                machine = data["machines"][(i - 1) % len(data["machines"])]
                sensor_type, unit, base_value, spread = sensor_profiles[i % len(sensor_profiles)]
                reading_time = start + timedelta(minutes=i * 5)
                warning = i % 29 == 0
                measurement = base_value + (Decimal(i % 100) / Decimal("100")) * spread
                if warning:
                    measurement += spread * Decimal("0.60")
                data["sensor_readings"].append({
                    "sensor_reading_id": 1400000 + i,
                    "machine_id": machine["machine_id"],
                    "sensor_type": sensor_type,
                    "reading_timestamp": reading_time.isoformat(),
                    "measurement": self._money(measurement),
                    "unit": unit,
                    "quality_flag": "warning" if warning else "normal",
                    "reason_code": "maintenance_watch" if warning else "not_applicable",
                })

        if need_products:
            data["products"] = []
            for i in range(1, product_count + 1):
                category = PRODUCT_CATEGORIES[i % len(PRODUCT_CATEGORIES)]
                unit_cost = Decimal(5 + (i % 450)) + Decimal(self.rng.randrange(0, 100)) / 100
                selling_price = unit_cost * Decimal("1.35")
                data["products"].append({
                    "product_id": 400000 + i,
                    "product_name": f"{category.replace('_', ' ').title()} Product {i:05d}",
                    "product_category": category,
                    "sku": f"MF-{category[:3].upper()}-{i:06d}",
                    "unit_cost": self._money(unit_cost),
                    "selling_price": self._money(selling_price),
                    "active_flag": i % 37 != 0,
                    "created_at": str(self.today - timedelta(days=200 + i % 1000)),
                })

        if need_suppliers:
            data["suppliers"] = []
            for i in range(1, supplier_count + 1):
                _, _, country = CITIES[i % len(CITIES)]
                data["suppliers"].append({
                    "supplier_id": 500000 + i,
                    "supplier_name": f"Supplier {i:05d}",
                    "country": country,
                    "rating": round(2.5 + (i % 25) / 10, 1),
                    "lead_time_days": 2 + (i % 45),
                    "status": "active" if i % 29 else SUPPLIER_STATUSES[i % len(SUPPLIER_STATUSES)],
                    "idempotency_key": f"MFG-SUP-{500000 + i}",
                    "created_at": str(self.today - timedelta(days=180 + i % 1200)),
                })

        if need_materials:
            data["raw_materials"] = []
            for i in range(1, material_count + 1):
                supplier = data["suppliers"][(i - 1) % len(data["suppliers"])]
                material_type = MATERIAL_TYPES[i % len(MATERIAL_TYPES)]
                data["raw_materials"].append({
                    "material_id": 600000 + i,
                    "supplier_id": supplier["supplier_id"],
                    "material_name": f"{material_type.replace('_', ' ').title()} {i:05d}",
                    "material_type": material_type,
                    "unit_of_measure": UNITS_OF_MEASURE[i % len(UNITS_OF_MEASURE)],
                    "cost_per_unit": self._money(Decimal("1.25") + Decimal(i % 200) / 10),
                    "reorder_level": 100 + (i % 5000),
                    "created_at": str(self.today - timedelta(days=160 + i % 900)),
                })

        if need_employees:
            data["employees"] = []
            for i in range(1, employee_count + 1):
                factory = data["factories"][(i - 1) % len(data["factories"])]
                role = EMPLOYEE_ROLES[i % len(EMPLOYEE_ROLES)]
                data["employees"].append({
                    "employee_id": 700000 + i,
                    "factory_id": factory["factory_id"],
                    "employee_name": full_name(i, "manufacturing.employee"),
                    "role": role,
                    "shift": SHIFTS[i % len(SHIFTS)],
                    "hire_date": str(self.today - timedelta(days=30 + i % 3000)),
                    "status": "active" if i % 41 else "inactive",
                    "created_at": str(self.today - timedelta(days=30 + i % 3000)),
                })

        if need_work_orders:
            data["work_orders"] = []
            for i in range(1, self.work_order_records + 1):
                line = data["production_lines"][(i - 1) % len(data["production_lines"])]
                product = data["products"][(i - 1) % len(data["products"])]
                planned = 100 + (i % 5000)
                rejected = i % 37
                produced = max(0, planned - rejected + (i % 11))
                status = "completed" if i % 13 else WORK_ORDER_STATUSES[i % len(WORK_ORDER_STATUSES)]
                planned_start = start + timedelta(hours=i % 720)
                planned_end = planned_start + timedelta(hours=4 + i % 12)
                actual_start = planned_start + timedelta(minutes=i % 45)
                actual_end = planned_end + timedelta(minutes=i % 90)
                data["work_orders"].append({
                    "work_order_id": 800000 + i,
                    "factory_id": line["factory_id"],
                    "line_id": line["line_id"],
                    "product_id": product["product_id"],
                    "planned_quantity": planned,
                    "produced_quantity": produced,
                    "rejected_quantity": rejected,
                    "expected_amount": planned,
                    "actual_amount": produced,
                    "risk_score": round(min(0.95, 0.08 + (rejected / max(1, planned)) + ((i % 23) / 200)), 3),
                    "idempotency_key": f"MFG-WO-{800000 + i}",
                    "status": status,
                    "planned_start_time": planned_start.isoformat(),
                    "planned_end_time": planned_end.isoformat(),
                    "actual_start_time": actual_start.isoformat() if actual_start else "",
                    "actual_end_time": actual_end.isoformat() if actual_end else "",
                    "created_at": planned_start.date().isoformat(),
                })

        if need_batches:
            data["production_batches"] = []
            for i in range(1, batch_count + 1):
                work_order = data["work_orders"][(i - 1) % len(data["work_orders"])]
                quantity = max(1, int(work_order["produced_quantity"] / max(1, batch_count // self.work_order_records)))
                rejected = min(quantity, i % 13)
                batch_start = datetime.fromisoformat(work_order["planned_start_time"]) + timedelta(minutes=i % 180)
                data["production_batches"].append({
                    "batch_id": 900000 + i,
                    "work_order_id": work_order["work_order_id"],
                    "product_id": work_order["product_id"],
                    "line_id": work_order["line_id"],
                    "batch_number": f"BATCH-{work_order['work_order_id']}-{i:04d}",
                    "quantity_produced": quantity,
                    "quantity_rejected": rejected,
                    "batch_start_time": batch_start.isoformat(),
                    "batch_end_time": (batch_start + timedelta(hours=1 + i % 6)).isoformat(),
                    "batch_status": "completed" if i % 17 else BATCH_STATUSES[i % len(BATCH_STATUSES)],
                    "created_at": batch_start.date().isoformat(),
                })

        if need_quality:
            inspectors = [employee for employee in data["employees"] if employee["role"] == "inspector"] or data["employees"]
            data["quality_checks"] = []
            for i in range(1, quality_count + 1):
                batch = data["production_batches"][(i - 1) % len(data["production_batches"])]
                defect_count_for_check = batch["quantity_rejected"] if i % 5 == 0 else 0
                result = "passed" if defect_count_for_check == 0 else ("rework_required" if i % 2 else "failed")
                pass_percentage = Decimal("99.5") if defect_count_for_check == 0 else max(Decimal("70.0"), Decimal("98.0") - Decimal(defect_count_for_check))
                checked_at = datetime.fromisoformat(batch["batch_end_time"]) + timedelta(minutes=i % 60)
                data["quality_checks"].append({
                    "quality_check_id": 1000000 + i,
                    "batch_id": batch["batch_id"],
                    "inspector_id": inspectors[(i - 1) % len(inspectors)]["employee_id"],
                    "check_type": QUALITY_CHECK_TYPES[i % len(QUALITY_CHECK_TYPES)],
                    "result": result,
                    "defect_count": defect_count_for_check,
                    "pass_percentage": str(pass_percentage.quantize(Decimal("0.01"))),
                    "scenario_status_code": result,
                    "risk_score": round(min(0.99, 0.05 + (defect_count_for_check / max(1, int(batch["quantity_produced"]))) + ((i % 19) / 250)), 3),
                    "idempotency_key": f"MFG-QC-{1000000 + i}",
                    "checked_at": checked_at.isoformat(),
                    "created_at": checked_at.date().isoformat(),
                })

        if need("defects"):
            data["defects"] = []
            failed_checks = [row for row in data["quality_checks"] if row["defect_count"] > 0] or data["quality_checks"]
            for i in range(1, defect_count + 1):
                quality_check = failed_checks[(i - 1) % len(failed_checks)]
                data["defects"].append({
                    "defect_id": 1100000 + i,
                    "quality_check_id": quality_check["quality_check_id"],
                    "batch_id": quality_check["batch_id"],
                    "defect_type": DEFECT_TYPES[i % len(DEFECT_TYPES)],
                    "severity": SEVERITIES[i % len(SEVERITIES)] if i % 19 == 0 else "low",
                    "defect_quantity": max(1, int(quality_check["defect_count"]) or i % 7 or 1),
                    "root_cause": ROOT_CAUSES[i % len(ROOT_CAUSES)],
                    "detected_at": quality_check["checked_at"],
                    "created_at": str(datetime.fromisoformat(quality_check["checked_at"]).date()),
                })

        if need("maintenance_orders"):
            technicians = [employee for employee in data["employees"] if employee["role"] == "technician"] or data["employees"]
            data["maintenance_orders"] = []
            for i in range(1, maintenance_count + 1):
                machine = data["machines"][(i - 1) % len(data["machines"])]
                scheduled = start + timedelta(hours=i * 3)
                status = "completed" if i % 11 else MAINTENANCE_STATUSES[i % len(MAINTENANCE_STATUSES)]
                downtime = 15 + (i % 360) if status == "completed" else 0
                data["maintenance_orders"].append({
                    "maintenance_id": 1200000 + i,
                    "machine_id": machine["machine_id"],
                    "technician_id": technicians[(i - 1) % len(technicians)]["employee_id"],
                    "maintenance_type": MAINTENANCE_TYPES[i % len(MAINTENANCE_TYPES)],
                    "priority": MAINTENANCE_PRIORITIES[i % len(MAINTENANCE_PRIORITIES)],
                    "status": status,
                    "issue_description": f"{machine['machine_type']} service order {i:06d}",
                    "scheduled_time": scheduled.isoformat(),
                    "completed_time": (scheduled + timedelta(minutes=downtime)).isoformat() if status == "completed" else "",
                    "downtime_minutes": downtime,
                    "cost": self._money(Decimal(100 + i % 5000)),
                    "created_at": scheduled.date().isoformat(),
                })

        if need("inventory"):
            data["inventory"] = []
            inventory_id = 1300000
            if need_materials:
                for material in data["raw_materials"]:
                    inventory_id += 1
                    factory = data["factories"][inventory_id % len(data["factories"])]
                    data["inventory"].append({
                        "inventory_id": inventory_id,
                        "factory_id": factory["factory_id"],
                        "material_id": material["material_id"],
                        "product_id": "",
                        "inventory_type": "raw_material",
                        "quantity_on_hand": 500 + inventory_id % 25000,
                        "reorder_level": material["reorder_level"],
                        "last_updated_at": (start + timedelta(minutes=inventory_id % 1440)).isoformat(),
                        "created_at": str(self.today - timedelta(days=inventory_id % 365)),
                    })
            if need_products:
                for product in data["products"]:
                    inventory_id += 1
                    factory = data["factories"][inventory_id % len(data["factories"])]
                    data["inventory"].append({
                        "inventory_id": inventory_id,
                        "factory_id": factory["factory_id"],
                        "material_id": "",
                        "product_id": product["product_id"],
                        "inventory_type": "finished_good",
                        "quantity_on_hand": 100 + inventory_id % 15000,
                        "reorder_level": 50 + inventory_id % 3000,
                        "last_updated_at": (start + timedelta(minutes=inventory_id % 1440)).isoformat(),
                        "created_at": str(self.today - timedelta(days=inventory_id % 365)),
                    })
            data["inventory"] = data["inventory"][:inventory_count]

        enriched = enrich_dataset(data, self.load_type, self.scd_type, MANUFACTURING_SPEC)
        # `batch_id` is both a Manufacturing business key and a shared audit column.
        # Preserve the Manufacturing primary key after audit enrichment.
        for index, row in enumerate(enriched.get("production_batches", []), 1):
            row["batch_id"] = 900000 + index
            row["record_hash"] = record_hash(row)
        batch_ids = [row["batch_id"] for row in enriched.get("production_batches", [])]
        if batch_ids:
            for index, row in enumerate(enriched.get("quality_checks", []), 1):
                row["batch_id"] = batch_ids[(index - 1) % len(batch_ids)]
                row["record_hash"] = record_hash(row)
        quality_by_id = {row["quality_check_id"]: row for row in enriched.get("quality_checks", [])}
        for row in enriched.get("defects", []):
            quality_check = quality_by_id.get(row.get("quality_check_id"))
            if quality_check:
                row["batch_id"] = quality_check["batch_id"]
                row["record_hash"] = record_hash(row)
        return enriched
