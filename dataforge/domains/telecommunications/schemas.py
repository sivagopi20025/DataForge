from __future__ import annotations

from ...model import DomainSpec, EventDefinition, ForeignKey, TableSchema, with_enterprise_columns
from .issue_injection import DATE_COLUMNS, NUMERIC_COLUMNS, TYPE_MISMATCH_COLUMNS
from .validations import BUSINESS_RULES


BASE_SCHEMAS: dict[str, TableSchema] = {
    "telecom_customers": TableSchema("customer_id", ("customer_id", "customer_name", "customer_type", "email", "phone_number", "country", "state", "city", "registration_date", "status", "created_at")),
    "plans": TableSchema("plan_id", ("plan_id", "plan_name", "plan_type", "monthly_fee", "voice_minutes_included", "sms_included", "data_gb_included", "roaming_enabled", "active_flag", "created_at")),
    "subscriptions": TableSchema("subscription_id", ("subscription_id", "customer_id", "plan_id", "subscription_type", "start_date", "end_date", "status", "billing_cycle", "created_at"), (ForeignKey("customer_id", "telecom_customers", "customer_id"), ForeignKey("plan_id", "plans", "plan_id"))),
    "sim_cards": TableSchema("sim_id", ("sim_id", "subscription_id", "iccid", "imsi", "phone_number", "activation_date", "status", "created_at"), (ForeignKey("subscription_id", "subscriptions", "subscription_id"),)),
    "devices": TableSchema("device_id", ("device_id", "subscription_id", "imei", "device_type", "manufacturer", "model", "os_type", "purchase_date", "status", "created_at"), (ForeignKey("subscription_id", "subscriptions", "subscription_id"),)),
    "network_regions": TableSchema("region_id", ("region_id", "region_name", "country", "state", "city", "coverage_type", "created_at")),
    "cell_towers": TableSchema("tower_id", ("tower_id", "region_id", "tower_code", "latitude", "longitude", "tower_type", "technology", "status", "installed_date", "created_at"), (ForeignKey("region_id", "network_regions", "region_id"),)),
    "call_detail_records": TableSchema("cdr_id", ("cdr_id", "subscription_id", "sim_id", "device_id", "tower_id", "caller_number", "receiver_number", "call_start_time", "call_end_time", "duration_seconds", "call_type", "call_status", "cost", "created_at"), (ForeignKey("subscription_id", "subscriptions", "subscription_id"), ForeignKey("sim_id", "sim_cards", "sim_id"), ForeignKey("device_id", "devices", "device_id"), ForeignKey("tower_id", "cell_towers", "tower_id"))),
    "sms_records": TableSchema("sms_id", ("sms_id", "subscription_id", "sim_id", "device_id", "tower_id", "sender_number", "receiver_number", "sent_time", "delivery_status", "message_type", "cost", "created_at"), (ForeignKey("subscription_id", "subscriptions", "subscription_id"), ForeignKey("sim_id", "sim_cards", "sim_id"), ForeignKey("device_id", "devices", "device_id"), ForeignKey("tower_id", "cell_towers", "tower_id"))),
    "data_sessions": TableSchema("session_id", ("session_id", "subscription_id", "sim_id", "device_id", "tower_id", "session_start_time", "session_end_time", "data_used_mb", "network_type", "session_status", "cost", "created_at"), (ForeignKey("subscription_id", "subscriptions", "subscription_id"), ForeignKey("sim_id", "sim_cards", "sim_id"), ForeignKey("device_id", "devices", "device_id"), ForeignKey("tower_id", "cell_towers", "tower_id"))),
    "billing_accounts": TableSchema("billing_account_id", ("billing_account_id", "customer_id", "account_number", "billing_address", "billing_email", "payment_method", "status", "created_at"), (ForeignKey("customer_id", "telecom_customers", "customer_id"),)),
    "invoices": TableSchema("invoice_id", ("invoice_id", "billing_account_id", "invoice_month", "total_voice_charges", "total_sms_charges", "total_data_charges", "taxes", "total_amount", "due_date", "status", "created_at"), (ForeignKey("billing_account_id", "billing_accounts", "billing_account_id"),)),
    "payments": TableSchema("payment_id", ("payment_id", "invoice_id", "payment_date", "payment_method", "payment_amount", "payment_status", "transaction_reference", "created_at"), (ForeignKey("invoice_id", "invoices", "invoice_id"),)),
    "network_events": TableSchema("network_event_id", ("network_event_id", "tower_id", "region_id", "event_type", "severity", "event_start_time", "event_end_time", "affected_users", "root_cause", "status", "created_at"), (ForeignKey("tower_id", "cell_towers", "tower_id"), ForeignKey("region_id", "network_regions", "region_id"))),
    "support_tickets": TableSchema("ticket_id", ("ticket_id", "customer_id", "subscription_id", "ticket_type", "priority", "status", "opened_at", "resolved_at", "resolution_summary", "created_at"), (ForeignKey("customer_id", "telecom_customers", "customer_id"), ForeignKey("subscription_id", "subscriptions", "subscription_id", nullable=True))),
}

FACT_TABLES = {"call_detail_records", "sms_records", "data_sessions", "invoices", "payments", "network_events", "support_tickets"}
DIMENSION_TABLES = {"telecom_customers", "subscriptions", "plans", "sim_cards", "devices", "cell_towers", "network_regions", "billing_accounts"}

TELECOMMUNICATIONS_SPEC = DomainSpec(
    name="telecommunications",
    source_system="DATAFORGE_TELECOMMUNICATIONS",
    schemas=with_enterprise_columns(BASE_SCHEMAS, FACT_TABLES, DIMENSION_TABLES),
    fact_tables=FACT_TABLES,
    dimension_tables=DIMENSION_TABLES,
    timestamp_sources={
        "call_detail_records": "call_start_time",
        "sms_records": "sent_time",
        "data_sessions": "session_start_time",
        "invoices": "due_date",
        "payments": "payment_date",
        "network_events": "event_start_time",
        "support_tickets": "opened_at",
    },
    date_columns=DATE_COLUMNS,
    numeric_columns=NUMERIC_COLUMNS,
    type_mismatch_columns=TYPE_MISMATCH_COLUMNS,
    event_definitions=(
        EventDefinition("cdr_event", "call_detail_records", "CALL_DETAIL_RECORDED", "cdr_id", "call_start_time"),
        EventDefinition("sms_event", "sms_records", "SMS_RECORDED", "sms_id", "sent_time"),
        EventDefinition("data_session_event", "data_sessions", "DATA_SESSION_RECORDED", "session_id", "session_start_time"),
        EventDefinition("network_alert_event", "network_events", "NETWORK_ALERT", "network_event_id", "event_start_time"),
        EventDefinition("support_ticket_event", "support_tickets", "SUPPORT_TICKET_UPDATED", "ticket_id", "opened_at"),
    ),
    cdc_tables=("subscriptions", "sim_cards", "devices", "invoices", "payments", "network_events", "support_tickets"),
    business_rules=BUSINESS_RULES,
)
