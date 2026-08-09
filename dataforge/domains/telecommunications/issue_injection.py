from __future__ import annotations

DATE_COLUMNS = {
    "telecom_customers": "registration_date",
    "subscriptions": "start_date",
    "plans": "created_at",
    "sim_cards": "activation_date",
    "devices": "purchase_date",
    "network_regions": "created_at",
    "cell_towers": "installed_date",
    "call_detail_records": "call_start_time",
    "sms_records": "sent_time",
    "data_sessions": "session_start_time",
    "billing_accounts": "created_at",
    "invoices": "due_date",
    "payments": "payment_date",
    "network_events": "event_start_time",
    "support_tickets": "opened_at",
}

NUMERIC_COLUMNS = {
    "plans": "monthly_fee",
    "call_detail_records": "duration_seconds",
    "sms_records": "cost",
    "data_sessions": "data_used_mb",
    "invoices": "total_amount",
    "payments": "payment_amount",
    "network_events": "affected_users",
}

TYPE_MISMATCH_COLUMNS = {
    "telecom_customers": "customer_type",
    "subscriptions": "status",
    "plans": "plan_type",
    "sim_cards": "iccid",
    "devices": "imei",
    "network_regions": "coverage_type",
    "cell_towers": "technology",
    "call_detail_records": "call_status",
    "sms_records": "delivery_status",
    "data_sessions": "network_type",
    "billing_accounts": "payment_method",
    "invoices": "status",
    "payments": "payment_status",
    "network_events": "severity",
    "support_tickets": "ticket_type",
}
