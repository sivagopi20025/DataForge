from __future__ import annotations

DATE_COLUMNS = {
    "factories": "opened_date",
    "production_lines": "created_at",
    "machines": "install_date",
    "products": "created_at",
    "suppliers": "created_at",
    "raw_materials": "created_at",
    "work_orders": "planned_start_time",
    "production_batches": "batch_start_time",
    "quality_checks": "checked_at",
    "defects": "detected_at",
    "maintenance_orders": "scheduled_time",
    "employees": "hire_date",
    "inventory": "last_updated_at",
    "sensor_readings": "reading_timestamp",
}

NUMERIC_COLUMNS = {
    "factories": "planned_capacity_amount",
    "production_lines": "capacity_per_hour",
    "products": "unit_cost",
    "suppliers": "lead_time_days",
    "raw_materials": "cost_per_unit",
    "work_orders": "planned_quantity",
    "production_batches": "quantity_produced",
    "quality_checks": "pass_percentage",
    "defects": "defect_quantity",
    "maintenance_orders": "downtime_minutes",
    "inventory": "quantity_on_hand",
    "sensor_readings": "measurement",
}

TYPE_MISMATCH_COLUMNS = {
    "factories": "factory_type",
    "production_lines": "product_category",
    "machines": "machine_type",
    "products": "sku",
    "suppliers": "rating",
    "raw_materials": "unit_of_measure",
    "work_orders": "status",
    "production_batches": "batch_status",
    "quality_checks": "result",
    "defects": "severity",
    "maintenance_orders": "priority",
    "employees": "role",
    "inventory": "inventory_type",
    "sensor_readings": "quality_flag",
}
