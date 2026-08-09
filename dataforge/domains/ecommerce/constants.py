from __future__ import annotations

CUSTOMER_SEGMENTS = ("new", "returning", "loyal", "high_value", "at_risk")
CUSTOMER_STATUSES = ("active", "inactive", "suspended", "deleted")
BUSINESS_TYPES = ("individual", "small_business", "enterprise", "distributor", "manufacturer")
SELLER_STATUSES = ("active", "suspended", "inactive", "pending_verification")
STORE_CATEGORIES = ("electronics", "fashion", "home", "grocery", "beauty", "books", "sports", "toys", "automotive")
PRODUCT_TYPES = ("physical", "digital", "subscription", "service")
LISTING_STATUSES = ("active", "inactive", "out_of_stock", "removed", "pending_approval")
FULFILLMENT_TYPES = ("marketplace_fulfilled", "seller_fulfilled", "dropship", "digital_delivery")
CART_STATUSES = ("active", "abandoned", "converted", "expired")
ORDER_STATUSES = ("placed", "confirmed", "packed", "shipped", "delivered", "cancelled", "returned", "refunded")
ORDER_SOURCES = ("cart", "direct_buy", "subscription", "api", "guest_checkout")
ITEM_STATUSES = ("ordered", "packed", "shipped", "delivered", "cancelled", "returned")
PAYMENT_METHODS = ("credit_card", "debit_card", "wallet", "bank_transfer", "gift_card", "cash_on_delivery")
PAYMENT_STATUSES = ("successful", "failed", "pending", "refunded", "partially_refunded")
CARRIERS = ("ups", "fedex", "usps", "dhl", "blue_dart", "delhivery", "amazon_shipping", "local_courier")
SHIPMENT_STATUSES = ("pending", "packed", "shipped", "in_transit", "delivered", "delayed", "lost", "returned")
RETURN_REASONS = ("damaged", "wrong_item", "not_as_described", "size_issue", "changed_mind", "defective", "late_delivery")
RETURN_STATUSES = ("requested", "approved", "rejected", "received", "refunded", "closed")
REVIEW_STATUSES = ("pending", "approved", "rejected", "flagged")
PROMOTION_TYPES = ("seasonal", "seller_coupon", "platform_coupon", "clearance", "first_purchase", "loyalty")
DISCOUNT_TYPES = ("percentage", "fixed_amount", "free_shipping")

CITIES = (
    ("Seattle", "Washington", "USA"),
    ("Austin", "Texas", "USA"),
    ("San Jose", "California", "USA"),
    ("Toronto", "Ontario", "Canada"),
    ("London", "England", "UK"),
    ("Bengaluru", "Karnataka", "India"),
)
FIRST_NAMES = ("Ava", "Noah", "Mia", "Liam", "Sophia", "Ethan", "Isabella", "Lucas", "Amelia", "Mason")
LAST_NAMES = ("Patel", "Smith", "Garcia", "Chen", "Brown", "Kumar", "Davis", "Wilson", "Martinez", "Lee")
BRANDS = ("Northstar", "UrbanNest", "VoltEdge", "Freshly", "Luma", "TrailPro", "BookHive", "AutoZen")
