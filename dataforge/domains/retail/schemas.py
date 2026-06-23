from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from ...model import DomainSpec, EventDefinition, ForeignKey, TableSchema, with_enterprise_columns


BASE_SCHEMAS: dict[str, TableSchema] = {
    "categories": TableSchema("category_id", ("category_id", "category_name", "department", "created_date", "status")),
    "suppliers": TableSchema("supplier_id", ("supplier_id", "supplier_name", "country", "rating", "created_date")),
    "stores": TableSchema("store_id", ("store_id", "store_name", "city", "state", "country", "open_date")),
    "customers": TableSchema("customer_id", ("customer_id", "first_name", "last_name", "email", "phone", "join_date", "loyalty_level")),
    "products": TableSchema("product_id", ("product_id", "category_id", "supplier_id", "sku", "product_name", "unit_price", "cost_price", "created_date", "status"), (ForeignKey("category_id", "categories", "category_id"), ForeignKey("supplier_id", "suppliers", "supplier_id"))),
    "employees": TableSchema("employee_id", ("employee_id", "store_id", "first_name", "last_name", "role", "hire_date", "salary"), (ForeignKey("store_id", "stores", "store_id"),)),
    "promotions": TableSchema("promotion_id", ("promotion_id", "product_id", "discount_pct", "start_date", "end_date"), (ForeignKey("product_id", "products", "product_id"),)),
    "inventory": TableSchema("inventory_id", ("inventory_id", "store_id", "product_id", "quantity_on_hand", "reorder_level", "snapshot_date"), (ForeignKey("store_id", "stores", "store_id"), ForeignKey("product_id", "products", "product_id"))),
    "sales": TableSchema("sale_id", ("sale_id", "store_id", "customer_id", "product_id", "promotion_id", "quantity", "unit_price", "sale_amount", "sale_timestamp", "payment_method"), (ForeignKey("store_id", "stores", "store_id"), ForeignKey("customer_id", "customers", "customer_id"), ForeignKey("product_id", "products", "product_id"), ForeignKey("promotion_id", "promotions", "promotion_id", nullable=True))),
    "payments": TableSchema("payment_id", ("payment_id", "sale_id", "customer_id", "amount", "payment_type", "payment_timestamp", "status"), (ForeignKey("sale_id", "sales", "sale_id"), ForeignKey("customer_id", "customers", "customer_id"))),
    "returns": TableSchema("return_id", ("return_id", "sale_id", "product_id", "customer_id", "return_reason", "return_amount", "return_date"), (ForeignKey("sale_id", "sales", "sale_id"), ForeignKey("product_id", "products", "product_id"), ForeignKey("customer_id", "customers", "customer_id"))),
    "purchase_orders": TableSchema("po_id", ("po_id", "supplier_id", "store_id", "order_date", "expected_delivery", "total_amount", "status"), (ForeignKey("supplier_id", "suppliers", "supplier_id"), ForeignKey("store_id", "stores", "store_id"))),
    "shipments": TableSchema("shipment_id", ("shipment_id", "po_id", "supplier_id", "shipment_date", "delivery_date", "status", "tracking_number"), (ForeignKey("po_id", "purchase_orders", "po_id"), ForeignKey("supplier_id", "suppliers", "supplier_id"))),
}

FACT_TABLES = {"sales", "payments", "returns", "shipments"}
DIMENSION_TABLES = {"categories", "products", "stores", "customers", "employees", "suppliers", "promotions"}


def _payment_cannot_exceed_sale(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    sales = {row["sale_id"]: row for row in data.get("sales", [])}
    failures = 0
    for payment in data.get("payments", []):
        sale = sales.get(payment.get("sale_id"))
        if not sale:
            continue
        try:
            failures += Decimal(str(payment["amount"])) > Decimal(str(sale["sale_amount"]))
        except InvalidOperation:
            failures += 1
    return [{"check": "payment_cannot_exceed_sale_amount", "table": "payments", "failures": failures}]


def _return_requires_sale(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    sale_ids = {row["sale_id"] for row in data.get("sales", [])}
    failures = sum(1 for row in data.get("returns", []) if row.get("sale_id") not in sale_ids)
    return [{"check": "return_must_have_sale", "table": "returns", "failures": failures}]


RETAIL_SPEC = DomainSpec(
    name="retail",
    source_system="DATAFORGE_RETAIL",
    schemas=with_enterprise_columns(BASE_SCHEMAS, FACT_TABLES, DIMENSION_TABLES),
    fact_tables=FACT_TABLES,
    dimension_tables=DIMENSION_TABLES,
    timestamp_sources={
        "sales": "sale_timestamp",
        "payments": "payment_timestamp",
        "returns": "return_date",
        "shipments": "delivery_date",
    },
    date_columns={
        "categories": "created_date", "suppliers": "created_date", "stores": "open_date",
        "customers": "join_date", "products": "created_date", "employees": "hire_date",
        "promotions": "start_date", "inventory": "snapshot_date", "sales": "sale_timestamp",
        "payments": "payment_timestamp", "returns": "return_date",
        "purchase_orders": "order_date", "shipments": "shipment_date",
    },
    numeric_columns={
        "suppliers": "rating", "products": "unit_price", "employees": "salary",
        "promotions": "discount_pct", "inventory": "quantity_on_hand", "sales": "sale_amount",
        "payments": "amount", "returns": "return_amount", "purchase_orders": "total_amount",
    },
    type_mismatch_columns={
        "categories": "category_name", "suppliers": "rating", "stores": "store_name",
        "customers": "first_name", "products": "unit_price", "employees": "salary",
        "promotions": "discount_pct", "inventory": "quantity_on_hand", "sales": "sale_amount",
        "payments": "amount", "returns": "return_amount", "purchase_orders": "total_amount",
        "shipments": "tracking_number",
    },
    event_definitions=(
        EventDefinition("sale_created", "sales", "SALE_CREATED", "sale_id"),
        EventDefinition("sale_updated", "sales", "SALE_UPDATED", "sale_id", sample_every=10),
        EventDefinition("sale_cancelled", "sales", "SALE_CANCELLED", "sale_id", sample_every=10),
        EventDefinition("payment_received", "payments", "PAYMENT_RECEIVED", "payment_id"),
        EventDefinition("inventory_adjusted", "inventory", "INVENTORY_ADJUSTED", "inventory_id"),
        EventDefinition("shipment_delivered", "shipments", "SHIPMENT_DELIVERED", "shipment_id"),
    ),
    cdc_tables=("sales",),
    business_rules=(_payment_cannot_exceed_sale, _return_requires_sale),
)
