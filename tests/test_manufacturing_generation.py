from dataforge.domains.manufacturing.generators import ManufacturingGenerator
from dataforge.domains.manufacturing.schemas import MANUFACTURING_SPEC
from dataforge.model import AUDIT_COLUMNS, TIME_HIERARCHY_COLUMNS
from dataforge.validation import schema_report, validate


EXPECTED_TABLES = {
    "factories",
    "production_lines",
    "machines",
    "products",
    "suppliers",
    "raw_materials",
    "work_orders",
    "production_batches",
    "quality_checks",
    "defects",
    "maintenance_orders",
    "employees",
    "inventory",
    "sensor_readings",
}


def test_manufacturing_generation_has_expected_tables_and_enterprise_columns():
    data = ManufacturingGenerator(120, seed=71, load_type="bulk", scd_type=2).generate()
    assert set(data) == EXPECTED_TABLES
    assert len(data["work_orders"]) == 120
    assert validate(data, MANUFACTURING_SPEC)["overall_status"] == "PASS"
    assert schema_report(data, MANUFACTURING_SPEC)["overall_status"] == "PASS"
    assert any(row["record_version"] == 2 for row in data["factories"])
    for table, rows in data.items():
        assert set(AUDIT_COLUMNS) <= set(rows[0])
        if table in MANUFACTURING_SPEC.fact_tables:
            assert set(TIME_HIERARCHY_COLUMNS) <= set(rows[0])


def test_manufacturing_quantities_are_business_consistent():
    data = ManufacturingGenerator(100, seed=72).generate()
    assert all(row["rejected_quantity"] <= row["produced_quantity"] for row in data["work_orders"])
    assert all(row["produced_quantity"] <= row["planned_quantity"] * 1.10 for row in data["work_orders"])
    assert all(row["quantity_rejected"] <= row["quantity_produced"] for row in data["production_batches"])
    assert all(row["downtime_minutes"] >= 0 for row in data["maintenance_orders"])
    assert all(float(row["measurement"]) >= 0 for row in data["sensor_readings"])
