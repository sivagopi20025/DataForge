from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from ...audit import enrich_dataset
from ...model import Dataset
from ...synthetic_values import full_name, unique_email
from .constants import (
    BRANDS,
    BUSINESS_TYPES,
    CARRIERS,
    CART_STATUSES,
    CITIES,
    CUSTOMER_SEGMENTS,
    CUSTOMER_STATUSES,
    DISCOUNT_TYPES,
    FIRST_NAMES,
    FULFILLMENT_TYPES,
    ITEM_STATUSES,
    LAST_NAMES,
    LISTING_STATUSES,
    ORDER_STATUSES,
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
from .schemas import ECOMMERCE_SPEC


class EcommerceGenerator:
    def __init__(self, order_records: int, seed: int = 42, load_type: str = "bulk", scd_type: int = 1) -> None:
        if order_records < 1:
            raise ValueError("records must be at least 1")
        self.order_records = order_records
        self.rng = random.Random(seed)
        self.load_type = load_type
        self.scd_type = scd_type
        self.today = date(2026, 6, 22)
        self.selected_tables: set[str] | None = None

    def _count(self, ratio: float, minimum: int, maximum: int | None = None) -> int:
        value = max(minimum, int(self.order_records * ratio))
        return min(value, maximum) if maximum else value

    def _money(self, value: Decimal) -> str:
        return str(value.quantize(Decimal("0.01")))

    def _name(self, index: int) -> str:
        return full_name(index, "ecommerce")

    def _required_tables(self) -> set[str]:
        if not self.selected_tables:
            return set(ECOMMERCE_SPEC.schemas)
        required = set(self.selected_tables)
        dependencies = {
            "seller_stores": {"sellers"},
            "product_categories": set(),
            "marketplace_products": {"product_categories"},
            "product_listings": {"marketplace_products", "seller_stores"},
            "carts": {"marketplace_customers"},
            "cart_items": {"carts", "product_listings"},
            "orders": {"marketplace_customers"},
            "order_items": {"orders", "product_listings"},
            "payments": {"orders"},
            "shipments": {"orders"},
            "returns": {"orders", "order_items"},
            "seller_payouts": {"sellers", "seller_stores", "product_listings", "orders", "payments"},
            "reviews": {"marketplace_customers", "marketplace_products", "orders"},
        }
        changed = True
        while changed:
            changed = False
            for table in tuple(required):
                missing = dependencies.get(table, set()) - required
                if missing:
                    required.update(missing)
                    changed = True
        return required

    def generate(self) -> Dataset:
        required = self._required_tables()

        def need(table: str) -> bool:
            return table in required

        customer_count = self._count(0.35, 100, 250000)
        seller_count = self._count(0.08, 25, 100000)
        store_count = self._count(0.10, 30, 120000)
        category_count = self._count(0.04, 12, 10000)
        product_count = self._count(0.45, 150, 500000)
        listing_count = self._count(0.55, 180, 600000)
        cart_count = self._count(0.50, 120, 300000)
        cart_item_count = max(1, int(self.order_records * 1.3))
        order_item_count = max(1, int(self.order_records * 1.6))
        payment_count = self.order_records
        shipment_count = self._count(0.90, 50, 250000)
        return_count = self._count(0.08, 8, 50000)
        payout_count = self._count(0.25, 25, 200000)
        review_count = self._count(0.20, 30, 150000)
        promotion_count = self._count(0.04, 10, 25000)
        start_dt = datetime(2026, 6, 1, 8, 0, 0) if self.load_type != "bulk" else datetime(2026, 1, 1, 8, 0, 0)
        data: Dataset = {}

        if need("marketplace_customers"):
            data["marketplace_customers"] = []
            for i in range(1, customer_count + 1):
                city, state, country = CITIES[i % len(CITIES)]
                registered = self.today - timedelta(days=20 + i % 2400)
                customer_name = self._name(i)
                data["marketplace_customers"].append({
                    "customer_id": 1000000 + i,
                    "customer_name": customer_name,
                    "email": unique_email(*customer_name.split(" ", 1), 1000000 + i, "ecommerce.customer"),
                    "phone_number": f"+1555{i:07d}"[-12:],
                    "country": country,
                    "state": state,
                    "city": city,
                    "registration_date": registered.isoformat(),
                    "customer_segment": CUSTOMER_SEGMENTS[i % len(CUSTOMER_SEGMENTS)],
                    "status": "active" if i % 37 else CUSTOMER_STATUSES[i % len(CUSTOMER_STATUSES)],
                    "created_at": registered.isoformat(),
                })

        if need("sellers"):
            data["sellers"] = []
            for i in range(1, seller_count + 1):
                city, state, country = CITIES[(i * 2) % len(CITIES)]
                registered = self.today - timedelta(days=45 + i % 1800)
                data["sellers"].append({
                    "seller_id": 2000000 + i,
                    "seller_name": f"{BRANDS[i % len(BRANDS)]} Seller {i:04d}",
                    "business_type": BUSINESS_TYPES[i % len(BUSINESS_TYPES)],
                    "country": country,
                    "state": state,
                    "city": city,
                    "registration_date": registered.isoformat(),
                    "seller_rating": round(3.2 + (i % 18) / 10, 1),
                    "status": "active" if i % 31 else SELLER_STATUSES[i % len(SELLER_STATUSES)],
                    "created_at": registered.isoformat(),
                })

        if need("seller_stores"):
            data["seller_stores"] = []
            for i in range(1, store_count + 1):
                seller = data["sellers"][(i - 1) % len(data["sellers"])]
                launched = self.today - timedelta(days=20 + i % 1600)
                category = STORE_CATEGORIES[i % len(STORE_CATEGORIES)]
                data["seller_stores"].append({
                    "store_id": 3000000 + i,
                    "seller_id": seller["seller_id"],
                    "store_name": f"{seller['seller_name']} {category.title()} Store",
                    "store_category": category,
                    "launch_date": launched.isoformat(),
                    "store_rating": round(3.1 + (i % 19) / 10, 1),
                    "status": "active" if i % 29 else SELLER_STATUSES[i % len(SELLER_STATUSES)],
                    "created_at": launched.isoformat(),
                })

        if need("product_categories"):
            data["product_categories"] = []
            for i in range(1, category_count + 1):
                parent_id = "" if i <= 5 else 4000000 + (i % 5) + 1
                data["product_categories"].append({
                    "category_id": 4000000 + i,
                    "parent_category_id": parent_id,
                    "category_name": STORE_CATEGORIES[i % len(STORE_CATEGORIES)].title() + f" {i:03d}",
                    "category_level": 1 if not parent_id else 2,
                    "active_flag": i % 41 != 0,
                    "created_at": (self.today - timedelta(days=1000 + i)).isoformat(),
                })

        if need("marketplace_products"):
            data["marketplace_products"] = []
            for i in range(1, product_count + 1):
                category = data["product_categories"][(i - 1) % len(data["product_categories"])]
                brand = BRANDS[i % len(BRANDS)]
                base_price = Decimal(8 + i % 900) + Decimal(self.rng.randrange(0, 100)) / 100
                data["marketplace_products"].append({
                    "product_id": 5000000 + i,
                    "category_id": category["category_id"],
                    "product_name": f"{brand} Product {i:06d}",
                    "brand": brand,
                    "manufacturer": f"{brand} Manufacturing",
                    "product_type": PRODUCT_TYPES[i % len(PRODUCT_TYPES)],
                    "base_price": self._money(base_price),
                    "active_flag": i % 43 != 0,
                    "created_at": (self.today - timedelta(days=700 + i % 1200)).isoformat(),
                })

        if need("product_listings"):
            data["product_listings"] = []
            for i in range(1, listing_count + 1):
                product = data["marketplace_products"][(i - 1) % len(data["marketplace_products"])]
                store = data["seller_stores"][(i - 1) % len(data["seller_stores"])]
                price = Decimal(product["base_price"]) * (Decimal("0.90") + Decimal(i % 30) / Decimal("100"))
                data["product_listings"].append({
                    "listing_id": 6000000 + i,
                    "product_id": product["product_id"],
                    "store_id": store["store_id"],
                    "listing_title": f"{store['store_name']} - {product['product_name']}",
                    "listing_price": self._money(price),
                    "available_quantity": 5 + i % 500,
                    "listing_status": "active" if i % 47 else LISTING_STATUSES[i % len(LISTING_STATUSES)],
                    "fulfillment_type": FULFILLMENT_TYPES[i % len(FULFILLMENT_TYPES)],
                    "created_at": (self.today - timedelta(days=300 + i % 500)).isoformat(),
                })

        if need("carts"):
            data["carts"] = []
            for i in range(1, cart_count + 1):
                customer = data["marketplace_customers"][(i - 1) % len(data["marketplace_customers"])]
                created = start_dt + timedelta(minutes=i * 3)
                data["carts"].append({
                    "cart_id": 7000000 + i,
                    "customer_id": customer["customer_id"],
                    "cart_status": CART_STATUSES[i % len(CART_STATUSES)],
                    "created_at": created.isoformat(),
                    "updated_at": (created + timedelta(minutes=5 + i % 90)).isoformat(),
                })

        if need("cart_items"):
            data["cart_items"] = []
            for i in range(1, cart_item_count + 1):
                cart = data["carts"][(i - 1) % len(data["carts"])]
                listing = data["product_listings"][(i - 1) % len(data["product_listings"])]
                added = datetime.fromisoformat(cart["created_at"]) + timedelta(minutes=1 + i % 30)
                data["cart_items"].append({
                    "cart_item_id": 8000000 + i,
                    "cart_id": cart["cart_id"],
                    "listing_id": listing["listing_id"],
                    "quantity": 1 + i % 4,
                    "unit_price": listing["listing_price"],
                    "added_at": added.isoformat(),
                    "created_at": added.isoformat(),
                })

        if need("orders"):
            data["orders"] = []
            for i in range(1, self.order_records + 1):
                customer = data["marketplace_customers"][(i - 1) % len(data["marketplace_customers"])]
                subtotal = Decimal(30 + i % 700)
                discount = Decimal(i % 20)
                tax = (subtotal - discount) * Decimal("0.0825")
                shipping = Decimal("0.00") if i % 5 == 0 else Decimal("6.99")
                total = subtotal - discount + tax + shipping
                ordered = start_dt + timedelta(minutes=i * 11)
                data["orders"].append({
                    "order_id": 9000000 + i,
                    "customer_id": customer["customer_id"],
                    "order_number": f"ORD-{ordered:%Y%m%d}-{i:08d}",
                    "order_date": ordered.isoformat(),
                    "order_status": "delivered" if i % 17 else ORDER_STATUSES[i % len(ORDER_STATUSES)],
                    "order_source": "cart" if i % 2 else "direct_buy",
                    "subtotal_amount": self._money(subtotal),
                    "discount_amount": self._money(discount),
                    "tax_amount": self._money(tax),
                    "shipping_amount": self._money(shipping),
                    "total_amount": self._money(total),
                    "created_at": ordered.isoformat(),
                })

        if need("order_items"):
            data["order_items"] = []
            for i in range(1, order_item_count + 1):
                order = data["orders"][(i - 1) % len(data["orders"])]
                listing = data["product_listings"][(i - 1) % len(data["product_listings"])]
                quantity = 1 + i % 3
                unit_price = Decimal(listing["listing_price"])
                discount = Decimal(i % 8)
                tax = (unit_price * quantity - discount) * Decimal("0.0825")
                line_total = unit_price * quantity - discount + tax
                data["order_items"].append({
                    "order_item_id": 10000000 + i,
                    "order_id": order["order_id"],
                    "listing_id": listing["listing_id"],
                    "quantity": quantity,
                    "unit_price": self._money(unit_price),
                    "discount_amount": self._money(discount),
                    "tax_amount": self._money(tax),
                    "line_total": self._money(line_total),
                    "item_status": "delivered" if i % 19 else ITEM_STATUSES[i % len(ITEM_STATUSES)],
                    "created_at": order["order_date"],
                })

        if need("payments"):
            data["payments"] = []
            for i in range(1, payment_count + 1):
                order = data["orders"][(i - 1) % len(data["orders"])]
                paid_at = datetime.fromisoformat(order["order_date"]) + timedelta(minutes=2)
                data["payments"].append({
                    "payment_id": 11000000 + i,
                    "order_id": order["order_id"],
                    "payment_method": PAYMENT_METHODS[i % len(PAYMENT_METHODS)],
                    "payment_amount": order["total_amount"],
                    "payment_status": "successful" if i % 23 else PAYMENT_STATUSES[i % len(PAYMENT_STATUSES)],
                    "transaction_reference": f"ECMPAY-{i:012d}",
                    "payment_date": paid_at.isoformat(),
                    "created_at": paid_at.isoformat(),
                })

        if need("shipments"):
            data["shipments"] = []
            for i in range(1, shipment_count + 1):
                order = data["orders"][(i - 1) % len(data["orders"])]
                shipped = datetime.fromisoformat(order["order_date"]) + timedelta(days=1 + i % 4)
                data["shipments"].append({
                    "shipment_id": 12000000 + i,
                    "order_id": order["order_id"],
                    "carrier": CARRIERS[i % len(CARRIERS)],
                    "tracking_number": f"TRK{i:014d}",
                    "shipment_status": "delivered" if i % 13 else SHIPMENT_STATUSES[i % len(SHIPMENT_STATUSES)],
                    "shipped_at": shipped.isoformat(),
                    "delivered_at": (shipped + timedelta(days=1 + i % 8)).isoformat(),
                    "shipping_cost": order["shipping_amount"],
                    "created_at": shipped.isoformat(),
                })

        if need("returns"):
            data["returns"] = []
            for i in range(1, return_count + 1):
                item = data["order_items"][(i - 1) % len(data["order_items"])]
                order = data["orders"][(i - 1) % len(data["orders"])]
                requested = datetime.fromisoformat(order["order_date"]) + timedelta(days=7 + i % 20)
                refund = min(Decimal(item["line_total"]), Decimal(order["total_amount"]))
                data["returns"].append({
                    "return_id": 13000000 + i,
                    "order_id": order["order_id"],
                    "order_item_id": item["order_item_id"],
                    "return_reason": RETURN_REASONS[i % len(RETURN_REASONS)],
                    "return_status": "refunded" if i % 5 else RETURN_STATUSES[i % len(RETURN_STATUSES)],
                    "refund_amount": self._money(refund),
                    "requested_at": requested.isoformat(),
                    "completed_at": (requested + timedelta(days=2 + i % 12)).isoformat(),
                    "created_at": requested.isoformat(),
                })

        if need("seller_payouts"):
            data["seller_payouts"] = []
            for i in range(1, payout_count + 1):
                payment = data["payments"][(i - 1) % len(data["payments"])]
                order = data["orders"][(i - 1) % len(data["orders"])]
                listing = data["product_listings"][(i - 1) % len(data["product_listings"])]
                store = next(row for row in data["seller_stores"] if row["store_id"] == listing["store_id"])
                created = datetime.fromisoformat(payment["payment_date"]) + timedelta(days=1 + i % 5)
                status = "completed" if i % 17 else ("held" if i % 34 else "failed")
                processed = created + timedelta(days=1 + i % 4)
                amount = Decimal(str(payment["payment_amount"])) * Decimal("0.82")
                data["seller_payouts"].append({
                    "seller_payout_id": 16000000 + i,
                    "seller_id": store["seller_id"],
                    "order_id": order["order_id"],
                    "payment_id": payment["payment_id"],
                    "payout_amount": self._money(amount),
                    "currency": "USD",
                    "payout_status": status,
                    "created_at": created.isoformat(),
                    "processed_at": processed.isoformat() if status == "completed" else "not_applicable",
                    "external_reference": f"POUT-{i:012d}",
                    "hold_reason": "risk_review" if status == "held" else "not_applicable",
                    "failure_reason": "bank_account_rejected" if status == "failed" else "not_applicable",
                })

        if need("reviews"):
            data["reviews"] = []
            for i in range(1, review_count + 1):
                customer = data["marketplace_customers"][(i - 1) % len(data["marketplace_customers"])]
                product = data["marketplace_products"][(i - 1) % len(data["marketplace_products"])]
                order = data["orders"][(i - 1) % len(data["orders"])]
                reviewed = datetime.fromisoformat(order["order_date"]) + timedelta(days=3 + i % 45)
                rating = 1 + i % 5
                data["reviews"].append({
                    "review_id": 14000000 + i,
                    "customer_id": customer["customer_id"],
                    "product_id": product["product_id"],
                    "order_id": order["order_id"] if i % 7 else "",
                    "rating": rating,
                    "review_title": f"{rating}-star marketplace review",
                    "review_text": f"Generated review {i:06d} for pipeline testing.",
                    "review_status": "approved" if i % 11 else REVIEW_STATUSES[i % len(REVIEW_STATUSES)],
                    "review_date": reviewed.isoformat(),
                    "created_at": reviewed.isoformat(),
                })

        if need("promotions"):
            data["promotions"] = []
            for i in range(1, promotion_count + 1):
                starts = start_dt.date() + timedelta(days=i % 120)
                discount_type = DISCOUNT_TYPES[i % len(DISCOUNT_TYPES)]
                data["promotions"].append({
                    "promotion_id": 15000000 + i,
                    "promotion_name": f"{PROMOTION_TYPES[i % len(PROMOTION_TYPES)].replace('_', ' ').title()} Promo {i:04d}",
                    "promotion_type": PROMOTION_TYPES[i % len(PROMOTION_TYPES)],
                    "discount_type": discount_type,
                    "discount_value": self._money(Decimal(5 + i % 40)),
                    "start_date": starts.isoformat(),
                    "end_date": (starts + timedelta(days=7 + i % 45)).isoformat(),
                    "active_flag": i % 17 != 0,
                    "created_at": starts.isoformat(),
                })

        return enrich_dataset(data, self.load_type, self.scd_type, ECOMMERCE_SPEC)
