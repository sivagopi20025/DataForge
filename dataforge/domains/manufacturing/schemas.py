from __future__ import annotations

from ...model import DomainSpec, EventDefinition, ForeignKey, TableSchema, with_enterprise_columns
from .issue_injection import DATE_COLUMNS, NUMERIC_COLUMNS, TYPE_MISMATCH_COLUMNS
from .validations import BUSINESS_RULES


BASE_SCHEMAS: dict[str, TableSchema] = {
    "factories": TableSchema("factory_id", ("factory_id", "factory_name", "country", "state", "city", "factory_type", "planned_capacity_amount", "opened_date", "status", "created_at")),
    "production_lines": TableSchema("line_id", ("line_id", "factory_id", "line_name", "product_category", "capacity_per_hour", "shift_count", "status", "risk_score", "idempotency_key", "created_at"), (ForeignKey("factory_id", "factories", "factory_id"),)),
    "machines": TableSchema("machine_id", ("machine_id", "line_id", "machine_name", "machine_type", "manufacturer", "install_date", "expected_life_years", "status", "created_at"), (ForeignKey("line_id", "production_lines", "line_id"),)),
    "sensor_readings": TableSchema("sensor_reading_id", ("sensor_reading_id", "machine_id", "sensor_type", "reading_timestamp", "measurement", "unit", "quality_flag", "reason_code"), (ForeignKey("machine_id", "machines", "machine_id"),)),
    "products": TableSchema("product_id", ("product_id", "product_name", "product_category", "sku", "unit_cost", "selling_price", "active_flag", "created_at")),
    "suppliers": TableSchema("supplier_id", ("supplier_id", "supplier_name", "country", "rating", "lead_time_days", "status", "idempotency_key", "created_at")),
    "raw_materials": TableSchema("material_id", ("material_id", "supplier_id", "material_name", "material_type", "unit_of_measure", "cost_per_unit", "reorder_level", "created_at"), (ForeignKey("supplier_id", "suppliers", "supplier_id"),)),
    "work_orders": TableSchema("work_order_id", ("work_order_id", "factory_id", "line_id", "product_id", "planned_quantity", "produced_quantity", "rejected_quantity", "expected_amount", "actual_amount", "risk_score", "idempotency_key", "status", "planned_start_time", "planned_end_time", "actual_start_time", "actual_end_time", "created_at"), (ForeignKey("factory_id", "factories", "factory_id"), ForeignKey("line_id", "production_lines", "line_id"), ForeignKey("product_id", "products", "product_id"))),
    "production_batches": TableSchema("batch_id", ("batch_id", "work_order_id", "product_id", "line_id", "batch_number", "quantity_produced", "quantity_rejected", "batch_start_time", "batch_end_time", "batch_status", "created_at"), (ForeignKey("work_order_id", "work_orders", "work_order_id"), ForeignKey("product_id", "products", "product_id"), ForeignKey("line_id", "production_lines", "line_id"))),
    "quality_checks": TableSchema("quality_check_id", ("quality_check_id", "batch_id", "inspector_id", "check_type", "result", "defect_count", "pass_percentage", "scenario_status_code", "risk_score", "idempotency_key", "checked_at", "created_at"), (ForeignKey("batch_id", "production_batches", "batch_id"), ForeignKey("inspector_id", "employees", "employee_id"))),
    "defects": TableSchema("defect_id", ("defect_id", "quality_check_id", "batch_id", "defect_type", "severity", "defect_quantity", "root_cause", "detected_at", "created_at"), (ForeignKey("quality_check_id", "quality_checks", "quality_check_id"), ForeignKey("batch_id", "production_batches", "batch_id"))),
    "maintenance_orders": TableSchema("maintenance_id", ("maintenance_id", "machine_id", "technician_id", "maintenance_type", "priority", "status", "issue_description", "scheduled_time", "completed_time", "downtime_minutes", "cost", "created_at"), (ForeignKey("machine_id", "machines", "machine_id"), ForeignKey("technician_id", "employees", "employee_id"))),
    "employees": TableSchema("employee_id", ("employee_id", "factory_id", "employee_name", "role", "shift", "hire_date", "status", "created_at"), (ForeignKey("factory_id", "factories", "factory_id"),)),
    "inventory": TableSchema("inventory_id", ("inventory_id", "factory_id", "material_id", "product_id", "inventory_type", "quantity_on_hand", "reorder_level", "last_updated_at", "created_at"), (ForeignKey("factory_id", "factories", "factory_id"), ForeignKey("material_id", "raw_materials", "material_id", nullable=True), ForeignKey("product_id", "products", "product_id", nullable=True))),
}

FACT_TABLES = {"work_orders", "production_batches", "quality_checks", "defects", "maintenance_orders", "inventory", "sensor_readings"}
DIMENSION_TABLES = {"factories", "production_lines", "machines", "products", "suppliers", "raw_materials", "employees"}

MANUFACTURING_SPEC = DomainSpec(
    name="manufacturing",
    source_system="DATAFORGE_MANUFACTURING",
    schemas=with_enterprise_columns(BASE_SCHEMAS, FACT_TABLES, DIMENSION_TABLES),
    fact_tables=FACT_TABLES,
    dimension_tables=DIMENSION_TABLES,
    timestamp_sources={
        "work_orders": "planned_start_time",
        "production_batches": "batch_start_time",
        "quality_checks": "checked_at",
        "defects": "detected_at",
        "maintenance_orders": "scheduled_time",
        "inventory": "last_updated_at",
        "sensor_readings": "reading_timestamp",
    },
    date_columns=DATE_COLUMNS,
    numeric_columns=NUMERIC_COLUMNS,
    type_mismatch_columns=TYPE_MISMATCH_COLUMNS,
    event_definitions=(
        EventDefinition("work_order_event", "work_orders", "WORK_ORDER_UPDATED", "work_order_id", "actual_start_time"),
        EventDefinition("batch_event", "production_batches", "BATCH_COMPLETED", "batch_id", "batch_start_time"),
        EventDefinition("quality_event", "quality_checks", "QUALITY_CHECK_RECORDED", "quality_check_id", "checked_at"),
        EventDefinition("maintenance_event", "maintenance_orders", "MAINTENANCE_UPDATED", "maintenance_id", "scheduled_time"),
        EventDefinition("sensor_reading_event", "sensor_readings", "SENSOR_READING_RECORDED", "sensor_reading_id", "reading_timestamp"),
    ),
    cdc_tables=("work_orders", "production_batches", "quality_checks", "maintenance_orders", "inventory", "sensor_readings"),
    business_rules=BUSINESS_RULES,
)
