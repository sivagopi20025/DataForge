from dataforge.domains.ecommerce.generators import EcommerceGenerator
from dataforge.domains.ecommerce.schemas import ECOMMERCE_SPEC
from dataforge.validation import relationship_report


def test_ecommerce_relationships_have_no_orphans():
    data = EcommerceGenerator(150, seed=103).generate()
    report = relationship_report(data, ECOMMERCE_SPEC)
    assert report["overall_status"] == "PASS"
    assert len(report["relationships"]) == 21


def test_ecommerce_relationship_validation_catches_orphan_order_customer():
    data = EcommerceGenerator(80, seed=104).generate()
    data["orders"][0]["customer_id"] = 999999999
    report = relationship_report(data, ECOMMERCE_SPEC)
    assert report["overall_status"] == "FAIL"
    assert any(
        item["child_table"] == "orders" and item["child_column"] == "customer_id"
        for item in report["relationships"]
        if item["status"] == "FAIL"
    )
