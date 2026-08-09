from __future__ import annotations

from ...model import DomainSpec, EventDefinition, ForeignKey, TableSchema, with_enterprise_columns
from .issue_injection import DATE_COLUMNS, NUMERIC_COLUMNS, TYPE_MISMATCH_COLUMNS
from .validations import BUSINESS_RULES


BASE_SCHEMAS: dict[str, TableSchema] = {
    "marketplace_customers": TableSchema("customer_id", ("customer_id", "customer_name", "email", "phone_number", "country", "state", "city", "registration_date", "customer_segment", "status", "created_at")),
    "sellers": TableSchema("seller_id", ("seller_id", "seller_name", "business_type", "country", "state", "city", "registration_date", "seller_rating", "status", "created_at")),
    "seller_stores": TableSchema("store_id", ("store_id", "seller_id", "store_name", "store_category", "launch_date", "store_rating", "status", "created_at"), (ForeignKey("seller_id", "sellers", "seller_id"),)),
    "product_categories": TableSchema("category_id", ("category_id", "parent_category_id", "category_name", "category_level", "active_flag", "created_at"), (ForeignKey("parent_category_id", "product_categories", "category_id", nullable=True),)),
    "marketplace_products": TableSchema("product_id", ("product_id", "category_id", "product_name", "brand", "manufacturer", "product_type", "base_price", "active_flag", "created_at"), (ForeignKey("category_id", "product_categories", "category_id"),)),
    "product_listings": TableSchema("listing_id", ("listing_id", "product_id", "store_id", "listing_title", "listing_price", "available_quantity", "listing_status", "fulfillment_type", "created_at"), (ForeignKey("product_id", "marketplace_products", "product_id"), ForeignKey("store_id", "seller_stores", "store_id"))),
    "carts": TableSchema("cart_id", ("cart_id", "customer_id", "cart_status", "created_at", "updated_at"), (ForeignKey("customer_id", "marketplace_customers", "customer_id"),)),
    "cart_items": TableSchema("cart_item_id", ("cart_item_id", "cart_id", "listing_id", "quantity", "unit_price", "added_at", "created_at"), (ForeignKey("cart_id", "carts", "cart_id"), ForeignKey("listing_id", "product_listings", "listing_id"))),
    "orders": TableSchema("order_id", ("order_id", "customer_id", "order_number", "order_date", "order_status", "order_source", "subtotal_amount", "discount_amount", "tax_amount", "shipping_amount", "total_amount", "created_at"), (ForeignKey("customer_id", "marketplace_customers", "customer_id"),)),
    "order_items": TableSchema("order_item_id", ("order_item_id", "order_id", "listing_id", "quantity", "unit_price", "discount_amount", "tax_amount", "line_total", "item_status", "created_at"), (ForeignKey("order_id", "orders", "order_id"), ForeignKey("listing_id", "product_listings", "listing_id"))),
    "payments": TableSchema("payment_id", ("payment_id", "order_id", "payment_method", "payment_amount", "payment_status", "transaction_reference", "payment_date", "created_at"), (ForeignKey("order_id", "orders", "order_id"),)),
    "shipments": TableSchema("shipment_id", ("shipment_id", "order_id", "carrier", "tracking_number", "shipment_status", "shipped_at", "delivered_at", "shipping_cost", "created_at"), (ForeignKey("order_id", "orders", "order_id"),)),
    "returns": TableSchema("return_id", ("return_id", "order_id", "order_item_id", "return_reason", "return_status", "refund_amount", "requested_at", "completed_at", "created_at"), (ForeignKey("order_id", "orders", "order_id"), ForeignKey("order_item_id", "order_items", "order_item_id"))),
    "seller_payouts": TableSchema("seller_payout_id", ("seller_payout_id", "seller_id", "order_id", "payment_id", "payout_amount", "currency", "payout_status", "created_at", "processed_at", "external_reference", "hold_reason", "failure_reason"), (ForeignKey("seller_id", "sellers", "seller_id"), ForeignKey("order_id", "orders", "order_id"), ForeignKey("payment_id", "payments", "payment_id"))),
    "reviews": TableSchema("review_id", ("review_id", "customer_id", "product_id", "order_id", "rating", "review_title", "review_text", "review_status", "review_date", "created_at"), (ForeignKey("customer_id", "marketplace_customers", "customer_id"), ForeignKey("product_id", "marketplace_products", "product_id"), ForeignKey("order_id", "orders", "order_id", nullable=True))),
    "promotions": TableSchema("promotion_id", ("promotion_id", "promotion_name", "promotion_type", "discount_type", "discount_value", "start_date", "end_date", "active_flag", "created_at")),
}

FACT_TABLES = {"carts", "cart_items", "orders", "order_items", "payments", "shipments", "returns", "seller_payouts", "reviews"}
DIMENSION_TABLES = {"marketplace_customers", "sellers", "seller_stores", "product_categories", "marketplace_products", "product_listings", "promotions"}

ECOMMERCE_SPEC = DomainSpec(
    name="ecommerce",
    source_system="DATAFORGE_ECOMMERCE",
    schemas=with_enterprise_columns(BASE_SCHEMAS, FACT_TABLES, DIMENSION_TABLES),
    fact_tables=FACT_TABLES,
    dimension_tables=DIMENSION_TABLES,
    timestamp_sources={
        "carts": "created_at",
        "cart_items": "added_at",
        "orders": "order_date",
        "order_items": "created_at",
        "payments": "payment_date",
        "shipments": "shipped_at",
        "returns": "requested_at",
        "seller_payouts": "created_at",
        "reviews": "review_date",
    },
    date_columns=DATE_COLUMNS,
    numeric_columns=NUMERIC_COLUMNS,
    type_mismatch_columns=TYPE_MISMATCH_COLUMNS,
    event_definitions=(
        EventDefinition("cart_update_event", "cart_items", "CART_ITEM_UPDATED", "cart_item_id", "added_at"),
        EventDefinition("checkout_event", "orders", "ORDER_PLACED", "order_id", "order_date"),
        EventDefinition("payment_event", "payments", "PAYMENT_UPDATED", "payment_id", "payment_date"),
        EventDefinition("shipment_event", "shipments", "SHIPMENT_UPDATED", "shipment_id", "shipped_at"),
        EventDefinition("return_event", "returns", "RETURN_UPDATED", "return_id", "requested_at"),
        EventDefinition("seller_payout_event", "seller_payouts", "SELLER_PAYOUT_UPDATED", "seller_payout_id", "created_at"),
        EventDefinition("review_event", "reviews", "REVIEW_UPDATED", "review_id", "review_date"),
    ),
    cdc_tables=("product_listings", "carts", "orders", "payments", "shipments", "returns", "seller_payouts", "reviews"),
    business_rules=BUSINESS_RULES,
)
