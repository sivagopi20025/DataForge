from dataforge.domains.telecommunications.generators import TelecommunicationsGenerator
from dataforge.domains.telecommunications.schemas import TELECOMMUNICATIONS_SPEC
from dataforge.validation import validate


def test_telecommunications_validations_catch_invalid_call_and_invoice():
    data = TelecommunicationsGenerator(80, seed=85).generate()
    data["call_detail_records"][0]["call_end_time"] = data["call_detail_records"][0]["call_start_time"]
    data["call_detail_records"][0]["duration_seconds"] = 999
    data["invoices"][0]["total_amount"] = "0.00"
    data["payments"][0]["payment_amount"] = "-1.00"
    report = validate(data, TELECOMMUNICATIONS_SPEC)
    failed = {check["check"] for check in report["checks"] if check["status"] == "FAIL"}
    assert "call_duration_matches_start_and_end" in failed
    assert "invoice_total_equals_charges_plus_taxes" in failed
    assert "payment_amount_non_negative" in failed


def test_telecommunications_validations_catch_network_and_ticket_time_errors():
    data = TelecommunicationsGenerator(80, seed=86).generate()
    data["network_events"][0]["affected_users"] = -10
    data["network_events"][0]["event_end_time"] = data["network_events"][0]["event_start_time"]
    data["support_tickets"][0]["resolved_at"] = data["support_tickets"][0]["opened_at"]
    report = validate(data, TELECOMMUNICATIONS_SPEC)
    failed = {check["check"] for check in report["checks"] if check["status"] == "FAIL"}
    assert "network_event_time_and_affected_users_valid" in failed
    assert "support_ticket_resolution_after_open" in failed
