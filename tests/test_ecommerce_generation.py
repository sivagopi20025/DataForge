from dataforge.domains.ecommerce.generators import EcommerceGenerator
from dataforge.domains.ecommerce.schemas import ECOMMERCE_SPEC
from dataforge.model import AUDIT_COLUMNS, TIME_HIERARCHY_COLUMNS
from dataforge.validation import schema_report, validate


EXPECTED_TABLES = {
    "marketplace_customers",
    "sellers",
    "seller_stores",
    "product_categories",
    "marketplace_products",
    "product_listings",
    "carts",
    "cart_items",
    "orders",
    "order_items",
    "payments",
    "shipments",
    "returns",
    "seller_payouts",
    "reviews",
    "promotions",
}


def test_ecommerce_generation_has_expected_tables_and_enterprise_columns():
    data = EcommerceGenerator(120, seed=101, load_type="bulk", scd_type=2).generate()
    assert set(data) == EXPECTED_TABLES
    assert len(data["orders"]) == 120
    assert validate(data, ECOMMERCE_SPEC)["overall_status"] == "PASS"
    assert schema_report(data, ECOMMERCE_SPEC)["overall_status"] == "PASS"
    assert any(row["record_version"] == 2 for row in data["marketplace_customers"])
    for table, rows in data.items():
        assert set(AUDIT_COLUMNS) <= set(rows[0])
        if table in ECOMMERCE_SPEC.fact_tables:
            assert set(TIME_HIERARCHY_COLUMNS) <= set(rows[0])


def test_ecommerce_amount_dates_quantities_and_ratings_are_business_consistent():
    data = EcommerceGenerator(100, seed=102).generate()
    assert all(float(row["available_quantity"]) >= 0 for row in data["product_listings"])
    assert all(int(row["quantity"]) > 0 for row in data["cart_items"])
    assert all(1 <= int(row["rating"]) <= 5 for row in data["reviews"])
    assert all(float(row["payment_amount"]) >= 0 for row in data["payments"])
    assert all(float(row["payout_amount"]) >= 0 for row in data["seller_payouts"])
    assert all(row["shipped_at"] < row["delivered_at"] for row in data["shipments"])
    assert all(row["requested_at"] < row["completed_at"] for row in data["returns"])
    assert all(row["start_date"] < row["end_date"] for row in data["promotions"])
