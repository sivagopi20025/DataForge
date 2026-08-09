from __future__ import annotations

from .common import scenario
from dataforge.scenarios.models import ScenarioVariation

SCENARIOS = [
    scenario(domain="telecommunications", scenario_id="telecom_tower_congestion", name="Telecom Tower Congestion", category="streaming", subcategory="network_congestion", issue_type="outliers", table="data_sessions", column="data_used_mb", affected_tables=["cell_towers", "call_detail_records", "sms_records", "data_sessions"], validations=["tower_congestion_detected"], business_problem="Tower congestion causes failed sessions, dropped calls, and delayed usage events.", technical_problem="Data-session usage outliers model congestion pressure while streaming variants can add delayed/dropped events.", tags=["tower", "congestion", "streaming"], aliases=["tower congestion"], modes=["both"], event_types=["data_session_event", "tower_outage_event"], profiles=["urban_consumer", "business", "enterprise"]),
    scenario(domain="telecommunications", scenario_id="telecom_network_outage", name="Telecom Network Outage", category="operational_failure", subcategory="outage", issue_type="missing_records", table="data_sessions", column="session_id", affected_tables=["cell_towers", "data_sessions", "support_tickets"], validations=["network_outage_detected"], business_problem="Network outages create missing usage and support spikes.", technical_problem="Selected data-session rows are removed to simulate outage gaps.", tags=["outage", "network"], aliases=["network outage"], modes=["both"], event_types=["tower_outage_event"]),
    scenario(domain="telecommunications", scenario_id="telecom_sms_delay", name="Telecom SMS Delay", category="temporal_sequence", subcategory="sms", issue_type="invalid_dates", table="sms_records", column="sent_time", affected_tables=["sms_records"], validations=["sms_delay_detected"], business_problem="SMS delays break SLA and notification pipelines.", technical_problem="SMS timestamps are moved to invalid/future values.", tags=["sms", "delay"], aliases=["sms delay"], modes=["both"], event_types=["sms_event"]),
    scenario(domain="telecommunications", scenario_id="telecom_billing_mismatch", name="Telecom Billing Mismatch", category="reconciliation", subcategory="billing", issue_type="negative_values", table="invoices", column="total_amount", affected_tables=["invoices", "data_sessions", "call_detail_records"], validations=["billing_mismatch_detected"], business_problem="Billing totals must reconcile with voice, SMS, data, and roaming usage.", technical_problem="Billing totals are changed to invalid negative values.", tags=["billing", "reconciliation"], aliases=["billing mismatch"]),
    scenario(domain="telecommunications", scenario_id="telecom_roaming_charge_error", name="Telecom Roaming Charge Error", category="business_rule", subcategory="roaming", issue_type="outliers", table="invoices", column="taxes", affected_tables=["invoices", "data_sessions"], validations=["roaming_charge_error_detected"], business_problem="Roaming charge errors create customer disputes and revenue leakage.", technical_problem="Roaming-like invoice charge values are mutated into outliers in the current schema.", tags=["roaming", "charge"], aliases=["roaming error"]),
]

SCENARIOS[0].supported_variations.append(
    ScenarioVariation(
        variation_id="delayed_network_events",
        name="Delayed network events",
        description="Adds delayed/out-of-order event timing to the telecom tower congestion streaming scenario.",
        supported_modes=["streaming"],
        recommended_severity="high",
        expected_validation_differences=["event_sequence_invalid"],
    )
)
