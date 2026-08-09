from dataforge.domains.manufacturing.generators import ManufacturingGenerator
from dataforge.domains.manufacturing.schemas import MANUFACTURING_SPEC
from dataforge.validation import validate


def test_manufacturing_validations_catch_invalid_quantities_and_statuses():
    data = ManufacturingGenerator(80, seed=75).generate()
    data["work_orders"][0]["produced_quantity"] = data["work_orders"][0]["planned_quantity"] * 2
    data["work_orders"][0]["rejected_quantity"] = data["work_orders"][0]["produced_quantity"] + 1
    data["quality_checks"][0]["result"] = "NOT_A_RESULT"
    data["maintenance_orders"][0]["downtime_minutes"] = -10
    report = validate(data, MANUFACTURING_SPEC)
    failed = {check["check"] for check in report["checks"] if check["status"] == "FAIL"}
    assert "work_order_quantities_consistent" in failed
    assert "quality_result_valid" in failed
    assert "maintenance_downtime_and_cost_non_negative" in failed


def test_manufacturing_validations_catch_inventory_reference_conflict():
    data = ManufacturingGenerator(80, seed=76).generate()
    data["inventory"][0]["inventory_type"] = "raw_material"
    data["inventory"][0]["product_id"] = data["products"][0]["product_id"]
    report = validate(data, MANUFACTURING_SPEC)
    assert any(check["check"] == "inventory_references_exactly_one_item_type" and check["status"] == "FAIL" for check in report["checks"])
