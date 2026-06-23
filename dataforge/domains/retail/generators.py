from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from ...audit import enrich_dataset
from ...model import Dataset
from .schemas import RETAIL_SPEC


FIRST_NAMES = ("Ava", "Liam", "Mia", "Noah", "Emma", "Ethan", "Zoe", "Lucas")
LAST_NAMES = ("Patel", "Smith", "Chen", "Garcia", "Brown", "Wilson", "Kim", "Davis")
CITIES = (("Atlanta", "GA"), ("Austin", "TX"), ("Boston", "MA"), ("Chicago", "IL"), ("Seattle", "WA"))
DEPARTMENTS = (("Electronics", "Technology"), ("Groceries", "Food"), ("Clothing", "Fashion"), ("Home", "Home Goods"), ("Sports", "Recreation"))


class RetailGenerator:
    def __init__(self, sales_records: int, seed: int = 42, load_type: str = "bulk", scd_type: int = 1) -> None:
        if sales_records < 1:
            raise ValueError("records must be at least 1")
        self.sales_records = sales_records
        self.rng = random.Random(seed)
        self.load_type = load_type
        self.scd_type = scd_type
        self.today = date(2026, 6, 22)

    def _count(self, ratio: float, minimum: int = 1, maximum: int | None = None) -> int:
        value = max(minimum, int(self.sales_records * ratio))
        return min(value, maximum) if maximum else value

    def _person(self, number: int) -> tuple[str, str]:
        return FIRST_NAMES[number % len(FIRST_NAMES)], LAST_NAMES[(number * 3) % len(LAST_NAMES)]

    def generate(self) -> Dataset:
        counts = {
            "categories": min(20, self._count(0.00002, 5)),
            "stores": min(50, self._count(0.00005, 3)),
            "products": min(5000, self._count(0.005, 25)),
            "customers": min(50000, self._count(0.05, 100)),
            "employees": min(500, self._count(0.0005, 10)),
            "suppliers": min(200, self._count(0.0002, 5)),
            "promotions": min(1000, self._count(0.001, 5)),
            "inventory": min(250000, self._count(0.25, 50)),
            "purchase_orders": min(100000, self._count(0.1, 10)),
        }
        data: Dataset = {}
        data["categories"] = [
            {"category_id": i, "category_name": DEPARTMENTS[(i - 1) % len(DEPARTMENTS)][0], "department": DEPARTMENTS[(i - 1) % len(DEPARTMENTS)][1], "created_date": str(self.today - timedelta(days=1000 + i)), "status": "ACTIVE"}
            for i in range(1, counts["categories"] + 1)
        ]
        countries = ("USA", "Canada", "Mexico", "Germany", "Japan")
        data["suppliers"] = [
            {"supplier_id": 500 + i, "supplier_name": f"Supplier {i:04d}", "country": countries[i % len(countries)], "rating": round(3 + self.rng.random() * 2, 1), "created_date": str(self.today - timedelta(days=500 + i))}
            for i in range(1, counts["suppliers"] + 1)
        ]
        data["stores"] = [
            {"store_id": i, "store_name": f"DataForge Store {i:03d}", "city": CITIES[(i - 1) % len(CITIES)][0], "state": CITIES[(i - 1) % len(CITIES)][1], "country": "USA", "open_date": str(self.today - timedelta(days=365 * ((i % 15) + 1)))}
            for i in range(1, counts["stores"] + 1)
        ]
        data["customers"] = []
        for i in range(1, counts["customers"] + 1):
            first, last = self._person(i)
            data["customers"].append({"customer_id": 100000 + i, "first_name": first, "last_name": last, "email": f"{first}.{last}.{i}@example.test".lower(), "phone": f"555-{i % 1000:03d}-{(i * 17) % 10000:04d}", "join_date": str(self.today - timedelta(days=i % 1800)), "loyalty_level": ("BRONZE", "SILVER", "GOLD", "PLATINUM")[i % 4]})
        data["products"] = []
        for i in range(1, counts["products"] + 1):
            cost = Decimal(self.rng.randrange(100, 20000)) / 100
            price = (cost * Decimal("1.35")).quantize(Decimal("0.01"))
            data["products"].append({"product_id": 1000 + i, "category_id": data["categories"][(i - 1) % len(data["categories"])]["category_id"], "supplier_id": data["suppliers"][(i - 1) % len(data["suppliers"])]["supplier_id"], "sku": f"SKU-{i:08d}", "product_name": f"Product {i:06d}", "unit_price": str(price), "cost_price": str(cost), "created_date": str(self.today - timedelta(days=i % 1200)), "status": "ACTIVE" if i % 20 else "DISCONTINUED"})
        data["employees"] = []
        for i in range(1, counts["employees"] + 1):
            first, last = self._person(i + 2)
            data["employees"].append({"employee_id": 200000 + i, "store_id": data["stores"][(i - 1) % len(data["stores"])]["store_id"], "first_name": first, "last_name": last, "role": ("Associate", "Manager", "Cashier", "Stocker")[i % 4], "hire_date": str(self.today - timedelta(days=i % 2500)), "salary": 32000 + (i % 70) * 1000})
        data["promotions"] = []
        for i in range(1, counts["promotions"] + 1):
            start = self.today - timedelta(days=i % 120)
            data["promotions"].append({"promotion_id": 300000 + i, "product_id": data["products"][(i - 1) % len(data["products"])]["product_id"], "discount_pct": (5, 10, 15, 20)[i % 4], "start_date": str(start), "end_date": str(start + timedelta(days=30))})
        data["inventory"] = [
            {"inventory_id": i, "store_id": data["stores"][(i - 1) % len(data["stores"])]["store_id"], "product_id": data["products"][(i * 7) % len(data["products"])]["product_id"], "quantity_on_hand": self.rng.randrange(0, 500), "reorder_level": self.rng.randrange(5, 50), "snapshot_date": str(self.today)}
            for i in range(1, counts["inventory"] + 1)
        ]
        start_time = datetime(2026, 1, 1)
        data["sales"] = []
        for i in range(1, self.sales_records + 1):
            product = data["products"][self.rng.randrange(len(data["products"]))]
            quantity = self.rng.randrange(1, 6)
            unit_price = Decimal(product["unit_price"])
            promo = data["promotions"][i % len(data["promotions"])] if i % 4 == 0 else None
            discount = Decimal(promo["discount_pct"]) / 100 if promo else Decimal(0)
            amount = (unit_price * quantity * (1 - discount)).quantize(Decimal("0.01"))
            timestamp = start_time + timedelta(seconds=i * 17)
            if self.load_type in {"incremental", "delta", "cdc", "event", "event_stream"}:
                timestamp = datetime(2026, 6, 21) + timedelta(seconds=i)
            data["sales"].append({"sale_id": i, "store_id": data["stores"][i % len(data["stores"])]["store_id"], "customer_id": data["customers"][self.rng.randrange(len(data["customers"]))]["customer_id"], "product_id": product["product_id"], "promotion_id": promo["promotion_id"] if promo else "", "quantity": quantity, "unit_price": str(unit_price), "sale_amount": str(amount), "sale_timestamp": timestamp.isoformat(), "payment_method": ("CARD", "CASH", "MOBILE")[i % 3]})
        data["payments"] = [{"payment_id": s["sale_id"], "sale_id": s["sale_id"], "customer_id": s["customer_id"], "amount": s["sale_amount"], "payment_type": s["payment_method"], "payment_timestamp": s["sale_timestamp"], "status": "COMPLETED"} for s in data["sales"]]
        return_count = max(1, int(self.sales_records * 0.05))
        data["returns"] = [{"return_id": i, "sale_id": s["sale_id"], "product_id": s["product_id"], "customer_id": s["customer_id"], "return_reason": ("DAMAGED", "WRONG_ITEM", "UNWANTED")[i % 3], "return_amount": s["sale_amount"], "return_date": str(self.today - timedelta(days=i % 30))} for i, s in enumerate(data["sales"][:return_count], 1)]
        data["purchase_orders"] = []
        for i in range(1, counts["purchase_orders"] + 1):
            order_date = self.today - timedelta(days=i % 180)
            data["purchase_orders"].append({"po_id": i, "supplier_id": data["suppliers"][i % len(data["suppliers"])]["supplier_id"], "store_id": data["stores"][i % len(data["stores"])]["store_id"], "order_date": str(order_date), "expected_delivery": str(order_date + timedelta(days=7)), "total_amount": str(Decimal(self.rng.randrange(10000, 1000000)) / 100), "status": ("OPEN", "SHIPPED", "DELIVERED")[i % 3]})
        data["shipments"] = [{"shipment_id": po["po_id"], "po_id": po["po_id"], "supplier_id": po["supplier_id"], "shipment_date": po["order_date"], "delivery_date": po["expected_delivery"], "status": "DELIVERED" if po["status"] == "DELIVERED" else "IN_TRANSIT", "tracking_number": f"DF{po['po_id']:014d}"} for po in data["purchase_orders"]]
        return enrich_dataset(data, self.load_type, self.scd_type, RETAIL_SPEC)
