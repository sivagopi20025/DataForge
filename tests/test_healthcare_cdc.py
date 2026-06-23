import json

from dataforge.domains.healthcare.generators import HealthcareGenerator
from dataforge.domains.healthcare.schemas import HEALTHCARE_SPEC
from dataforge.modes import build_artifacts


def test_healthcare_cdc_generates_insert_update_delete_for_claims():
    data = HealthcareGenerator(50, seed=36, load_type="cdc").generate()
    artifacts = build_artifacts(data, "cdc", seed=36, selected_tables={"claims"}, spec=HEALTHCARE_SPEC)
    assert set(artifacts) == {"cdc/claims_cdc"}
    event_types = {row["event_type"] for row in artifacts["cdc/claims_cdc"]}
    assert {"INSERT", "UPDATE", "DELETE"} <= event_types
    payload = next(row["after_value"] or row["before_value"] for row in artifacts["cdc/claims_cdc"])
    assert "claim_id" in json.loads(payload)


def test_healthcare_cdc_supports_patients_visits_claims_payments():
    data = HealthcareGenerator(20, seed=37, load_type="cdc").generate()
    artifacts = build_artifacts(data, "cdc", seed=37, selected_tables={"patients", "visits", "claims", "payments"}, spec=HEALTHCARE_SPEC)
    assert set(artifacts) == {"cdc/patients_cdc", "cdc/visits_cdc", "cdc/claims_cdc", "cdc/payments_cdc"}
