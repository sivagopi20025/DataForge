from dataforge.domains.telecommunications.generators import TelecommunicationsGenerator
from dataforge.domains.telecommunications.schemas import TELECOMMUNICATIONS_SPEC
from dataforge.model import AUDIT_COLUMNS, TIME_HIERARCHY_COLUMNS
from dataforge.validation import schema_report, validate


EXPECTED_TABLES = {
    "telecom_customers",
    "subscriptions",
    "plans",
    "sim_cards",
    "devices",
    "cell_towers",
    "network_regions",
    "call_detail_records",
    "sms_records",
    "data_sessions",
    "billing_accounts",
    "invoices",
    "payments",
    "network_events",
    "support_tickets",
}


def test_telecommunications_generation_has_expected_tables_and_enterprise_columns():
    data = TelecommunicationsGenerator(120, seed=81, load_type="bulk", scd_type=2).generate()
    assert set(data) == EXPECTED_TABLES
    assert len(data["call_detail_records"]) == 120
    assert validate(data, TELECOMMUNICATIONS_SPEC)["overall_status"] == "PASS"
    assert schema_report(data, TELECOMMUNICATIONS_SPEC)["overall_status"] == "PASS"
    assert any(row["record_version"] == 2 for row in data["telecom_customers"])
    for table, rows in data.items():
        assert set(AUDIT_COLUMNS) <= set(rows[0])
        if table in TELECOMMUNICATIONS_SPEC.fact_tables:
            assert set(TIME_HIERARCHY_COLUMNS) <= set(rows[0])


def test_telecommunications_temporal_and_amounts_are_business_consistent():
    data = TelecommunicationsGenerator(100, seed=82).generate()
    assert all(row["call_end_time"] > row["call_start_time"] for row in data["call_detail_records"])
    assert all(int(row["duration_seconds"]) >= 0 for row in data["call_detail_records"])
    assert all(row["session_end_time"] > row["session_start_time"] for row in data["data_sessions"])
    assert all(float(row["data_used_mb"]) >= 0 for row in data["data_sessions"])
    assert all(float(row["payment_amount"]) >= 0 for row in data["payments"])
    assert all(row["affected_users"] >= 0 for row in data["network_events"])
