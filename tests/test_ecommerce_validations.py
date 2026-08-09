from dataforge.domains.ecommerce.generators import EcommerceGenerator
from dataforge.domains.ecommerce.schemas import ECOMMERCE_SPEC
from dataforge.validation import validate


def test_ecommerce_validations_catch_amount_date_quantity_and_rating_errors():
    data = EcommerceGenerator(80, seed=105).generate()
    data["orders"][0]["total_amount"] = "0.00"
    data["order_items"][0]["line_total"] = "0.00"
    data["payments"][0]["payment_amount"] = "-1.00"
    data["returns"][0]["refund_amount"] = "999999.00"
    data["shipments"][0]["delivered_at"] = data["shipments"][0]["shipped_at"]
    data["promotions"][0]["end_date"] = data["promotions"][0]["start_date"]
    data["product_listings"][0]["available_quantity"] = -1
    data["cart_items"][0]["quantity"] = 0
    data["reviews"][0]["rating"] = 6
    report = validate(data, ECOMMERCE_SPEC)
    failed = {check["check"] for check in report["checks"] if check["status"] == "FAIL"}
    assert "order_total_matches_components" in failed
    assert "order_item_line_total_matches_components" in failed
    assert "payment_amount_valid" in failed
    assert "return_refund_and_dates_valid" in failed
    assert "shipment_dates_and_cost_valid" in failed
    assert "promotion_dates_and_discount_valid" in failed
    assert "marketplace_quantities_and_ratings_valid" in failed


def test_ecommerce_validation_report_uses_standard_contract():
    data = EcommerceGenerator(40, seed=106).generate()
    report = validate(data, ECOMMERCE_SPEC, run_id="ecommerce-run-1", load_type="bulk", file_format="json")
    assert set(report) >= {
        "run_id",
        "domain",
        "load_type",
        "format",
        "record_count",
        "quality_score",
        "status",
        "summary",
        "issues",
        "checks",
        "generated_at",
    }
    assert report["domain"] == "ecommerce"
    assert report["quality_score"] == 100
    assert report["status"] == "PASS"
