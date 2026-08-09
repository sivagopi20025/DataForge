from dataforge.domains.manufacturing.generators import ManufacturingGenerator
from dataforge.domains.manufacturing.schemas import MANUFACTURING_SPEC
from dataforge.validation import relationship_report


def test_manufacturing_relationships_have_no_orphans():
    data = ManufacturingGenerator(150, seed=73).generate()
    report = relationship_report(data, MANUFACTURING_SPEC)
    assert report["overall_status"] == "PASS"
    assert len(report["relationships"]) == 20


def test_manufacturing_relationship_validation_catches_orphan_batch():
    data = ManufacturingGenerator(80, seed=74).generate()
    data["production_batches"][0]["work_order_id"] = 999999999
    report = relationship_report(data, MANUFACTURING_SPEC)
    assert report["overall_status"] == "FAIL"
    assert any(
        item["child_table"] == "production_batches" and item["child_column"] == "work_order_id"
        for item in report["relationships"]
        if item["status"] == "FAIL"
    )
