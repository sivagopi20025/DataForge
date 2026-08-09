from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .constants import (
    BUSINESS_TYPES,
    CARRIERS,
    CART_STATUSES,
    CUSTOMER_SEGMENTS,
    CUSTOMER_STATUSES,
    DISCOUNT_TYPES,
    FULFILLMENT_TYPES,
    ITEM_STATUSES,
    LISTING_STATUSES,
    ORDER_STATUSES,
    ORDER_SOURCES,
    PAYMENT_METHODS,
    PAYMENT_STATUSES,
    PRODUCT_TYPES,
    PROMOTION_TYPES,
    RETURN_REASONS,
    RETURN_STATUSES,
    REVIEW_STATUSES,
    SELLER_STATUSES,
    SHIPMENT_STATUSES,
    STORE_CATEGORIES,
)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _dt(value: Any) -> datetime:
    return datetime.fromisoformat(str(value))


def valid_value_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    checks = (
        ("customer_segment_valid", "marketplace_customers", "customer_segment", CUSTOMER_SEGMENTS),
        ("customer_status_valid", "marketplace_customers", "status", CUSTOMER_STATUSES),
        ("seller_business_type_valid", "sellers", "business_type", BUSINESS_TYPES),
        ("seller_status_valid", "sellers", "status", SELLER_STATUSES),
        ("store_category_valid", "seller_stores", "store_category", STORE_CATEGORIES),
        ("product_type_valid", "marketplace_products", "product_type", PRODUCT_TYPES),
        ("listing_status_valid", "product_listings", "listing_status", LISTING_STATUSES),
        ("fulfillment_type_valid", "product_listings", "fulfillment_type", FULFILLMENT_TYPES),
        ("cart_status_valid", "carts", "cart_status", CART_STATUSES),
        ("order_status_valid", "orders", "order_status", ORDER_STATUSES),
        ("order_source_valid", "orders", "order_source", ORDER_SOURCES),
        ("item_status_valid", "order_items", "item_status", ITEM_STATUSES),
        ("payment_method_valid", "payments", "payment_method", PAYMENT_METHODS),
        ("payment_status_valid", "payments", "payment_status", PAYMENT_STATUSES),
        ("carrier_valid", "shipments", "carrier", CARRIERS),
        ("shipment_status_valid", "shipments", "shipment_status", SHIPMENT_STATUSES),
        ("return_reason_valid", "returns", "return_reason", RETURN_REASONS),
        ("return_status_valid", "returns", "return_status", RETURN_STATUSES),
        ("review_status_valid", "reviews", "review_status", REVIEW_STATUSES),
        ("promotion_type_valid", "promotions", "promotion_type", PROMOTION_TYPES),
        ("discount_type_valid", "promotions", "discount_type", DISCOUNT_TYPES),
    )
    return [
        {"check": name, "table": table, "failures": sum(1 for row in data.get(table, []) if row.get(column) not in allowed)}
        for name, table, column, allowed in checks
    ]


def order_total_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = 0
    for row in data.get("orders", []):
        try:
            expected = _decimal(row["subtotal_amount"]) - _decimal(row["discount_amount"]) + _decimal(row["tax_amount"]) + _decimal(row["shipping_amount"])
            failures += abs(expected - _decimal(row["total_amount"])) > Decimal("0.02")
        except (InvalidOperation, KeyError):
            failures += 1
    return [{"check": "order_total_matches_components", "table": "orders", "failures": failures}]


def order_item_total_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = 0
    for row in data.get("order_items", []):
        try:
            expected = _decimal(row["quantity"]) * _decimal(row["unit_price"]) - _decimal(row["discount_amount"]) + _decimal(row["tax_amount"])
            failures += abs(expected - _decimal(row["line_total"])) > Decimal("0.02")
            failures += int(row["quantity"]) <= 0
        except (InvalidOperation, KeyError, ValueError, TypeError):
            failures += 1
    return [{"check": "order_item_line_total_matches_components", "table": "order_items", "failures": failures}]


def payment_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    order_totals = {row["order_id"]: _decimal(row["total_amount"]) for row in data.get("orders", []) if "order_id" in row and "total_amount" in row}
    failures = 0
    for row in data.get("payments", []):
        try:
            amount = _decimal(row["payment_amount"])
            failures += amount < 0
            if row.get("payment_status") == "successful" and row.get("order_id") in order_totals:
                failures += abs(amount - order_totals[row["order_id"]]) > Decimal("0.02")
        except (InvalidOperation, KeyError):
            failures += 1
    return [{"check": "payment_amount_valid", "table": "payments", "failures": failures}]


def return_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    item_totals = {row["order_item_id"]: _decimal(row["line_total"]) for row in data.get("order_items", []) if "order_item_id" in row and "line_total" in row}
    order_totals = {row["order_id"]: _decimal(row["total_amount"]) for row in data.get("orders", []) if "order_id" in row and "total_amount" in row}
    failures = 0
    for row in data.get("returns", []):
        try:
            refund = _decimal(row["refund_amount"])
            failures += refund < 0
            if row.get("order_item_id") in item_totals:
                failures += refund > item_totals[row["order_item_id"]]
            if row.get("order_id") in order_totals:
                failures += refund > order_totals[row["order_id"]]
            if row.get("completed_at"):
                failures += _dt(row["completed_at"]) <= _dt(row["requested_at"])
        except (InvalidOperation, KeyError, ValueError, TypeError):
            failures += 1
    return [{"check": "return_refund_and_dates_valid", "table": "returns", "failures": failures}]


def shipment_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = 0
    for row in data.get("shipments", []):
        try:
            failures += _decimal(row["shipping_cost"]) < 0
            if row.get("shipped_at") and row.get("delivered_at"):
                failures += _dt(row["delivered_at"]) <= _dt(row["shipped_at"])
        except (InvalidOperation, KeyError, ValueError, TypeError):
            failures += 1
    return [{"check": "shipment_dates_and_cost_valid", "table": "shipments", "failures": failures}]


def promotion_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = 0
    for row in data.get("promotions", []):
        try:
            failures += _dt(row["end_date"]) <= _dt(row["start_date"])
            failures += _decimal(row["discount_value"]) < 0
        except (InvalidOperation, KeyError, ValueError, TypeError):
            failures += 1
    return [{"check": "promotion_dates_and_discount_valid", "table": "promotions", "failures": failures}]


def marketplace_quantity_and_rating_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    failures = 0
    for row in data.get("product_listings", []):
        try:
            failures += int(row["available_quantity"]) < 0
        except (KeyError, ValueError, TypeError):
            failures += 1
    for row in data.get("cart_items", []):
        try:
            failures += int(row["quantity"]) <= 0
        except (KeyError, ValueError, TypeError):
            failures += 1
    for row in data.get("reviews", []):
        try:
            rating = int(row["rating"])
            failures += rating < 1 or rating > 5
        except (KeyError, ValueError, TypeError):
            failures += 1
    return [{"check": "marketplace_quantities_and_ratings_valid", "table": "marketplace", "failures": failures}]


def seller_payout_validation(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    valid_statuses = {"completed", "held", "failed", "pending"}
    failures = 0
    for row in data.get("seller_payouts", []):
        try:
            status = row.get("payout_status")
            failures += status not in valid_statuses
            failures += _decimal(row["payout_amount"]) < 0
            failures += bool(row.get("external_reference")) is False
            if status == "completed":
                failures += _dt(row["processed_at"]) <= _dt(row["created_at"])
                failures += row.get("hold_reason") != "not_applicable"
                failures += row.get("failure_reason") != "not_applicable"
            if status == "held":
                failures += row.get("hold_reason") == "not_applicable"
                failures += row.get("processed_at") != "not_applicable"
            if status == "failed":
                failures += row.get("failure_reason") == "not_applicable"
                failures += row.get("processed_at") != "not_applicable"
        except (InvalidOperation, KeyError, ValueError, TypeError):
            failures += 1
    return [{"check": "seller_payout_status_and_amount_valid", "table": "seller_payouts", "failures": failures}]


BUSINESS_RULES = (
    valid_value_validation,
    order_total_validation,
    order_item_total_validation,
    payment_validation,
    return_validation,
    shipment_validation,
    promotion_validation,
    marketplace_quantity_and_rating_validation,
    seller_payout_validation,
)
