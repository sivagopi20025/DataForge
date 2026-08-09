from __future__ import annotations

CUSTOMER_TYPES = ("individual", "business", "enterprise", "government")
CUSTOMER_STATUSES = ("active", "suspended", "inactive", "churned")
PLAN_TYPES = ("prepaid", "postpaid", "family", "business", "enterprise", "iot")
SUBSCRIPTION_TYPES = ("mobile", "broadband", "fiber", "fixed_wireless", "iot")
SUBSCRIPTION_STATUSES = ("active", "suspended", "cancelled", "expired", "pending_activation")
BILLING_CYCLES = ("monthly", "quarterly", "annual")
SIM_STATUSES = ("active", "inactive", "suspended", "lost", "replaced")
DEVICE_TYPES = ("smartphone", "tablet", "router", "iot_device", "modem", "wearable")
OS_TYPES = ("android", "ios", "windows", "linux", "embedded", "unknown")
COVERAGE_TYPES = ("urban", "suburban", "rural", "mixed")
TOWER_TYPES = ("macro", "micro", "small_cell", "rooftop", "indoor")
TECHNOLOGIES = ("4g", "5g", "lte", "fiber_backhaul", "mixed")
CALL_TYPES = ("local", "national", "international", "roaming", "emergency")
CALL_STATUSES = ("completed", "dropped", "failed", "busy", "no_answer")
DELIVERY_STATUSES = ("delivered", "failed", "pending", "expired")
MESSAGE_TYPES = ("sms", "mms", "otp", "promotional", "transactional")
NETWORK_TYPES = ("3g", "4g", "5g", "lte", "wifi_offload")
SESSION_STATUSES = ("completed", "dropped", "failed", "timed_out")
PAYMENT_METHODS = ("credit_card", "debit_card", "bank_transfer", "wallet", "autopay", "cash")
INVOICE_STATUSES = ("generated", "paid", "overdue", "cancelled", "disputed")
PAYMENT_STATUSES = ("successful", "failed", "pending", "refunded")
NETWORK_EVENT_TYPES = ("tower_outage", "high_latency", "packet_loss", "congestion", "power_failure", "backhaul_failure", "maintenance", "signal_degradation")
SEVERITIES = ("low", "medium", "high", "critical")
NETWORK_EVENT_STATUSES = ("open", "investigating", "resolved", "closed")
TICKET_TYPES = ("billing", "network_issue", "sim_replacement", "plan_change", "device_issue", "cancellation", "technical_support")
TICKET_PRIORITIES = ("low", "medium", "high", "urgent")
TICKET_STATUSES = ("open", "in_progress", "resolved", "closed", "escalated")
DEVICE_MANUFACTURERS = ("Apple", "Samsung", "Nokia", "Cisco", "Ericsson", "Motorola", "Huawei")

CITIES = (
    ("New York", "NY", "USA"),
    ("Dallas", "TX", "USA"),
    ("Atlanta", "GA", "USA"),
    ("Chicago", "IL", "USA"),
    ("Seattle", "WA", "USA"),
    ("Toronto", "ON", "Canada"),
    ("London", "ENG", "UK"),
)

FIRST_NAMES = ("Ava", "Liam", "Mia", "Noah", "Emma", "Ethan", "Zoe", "Lucas", "Ivy", "Owen")
LAST_NAMES = ("Patel", "Smith", "Chen", "Garcia", "Brown", "Wilson", "Kim", "Davis", "Miller", "Nguyen")
