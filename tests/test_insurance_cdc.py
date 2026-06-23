import json

from dataforge.domains.insurance.generators import InsuranceGenerator
from dataforge.domains.insurance.schemas import INSURANCE_SPEC
from dataforge.modes import build_artifacts


def test_insurance_cdc_generates_insert_update_delete_for_claims():
    data = InsuranceGenerator(50, seed=67, load_type="cdc").generate()
    artifacts = build_artifacts(data, "cdc", seed=67, selected_tables={"claims"}, spec=INSURANCE_SPEC)
    assert set(artifacts) == {"cdc/claims_cdc"}
    event_types = {row["event_type"] for row in artifacts["cdc/claims_cdc"]}
    assert {"INSERT", "UPDATE", "DELETE"} <= event_types
    payload = next(row["after_value"] or row["before_value"] for row in artifacts["cdc/claims_cdc"])
    assert "claim_id" in json.loads(payload)


def test_insurance_cdc_supports_policies_premiums_claims_settlements():
    data = InsuranceGenerator(20, seed=68, load_type="cdc").generate()
    artifacts = build_artifacts(data, "cdc", seed=68, selected_tables={"policies", "premiums", "claims", "settlements"}, spec=INSURANCE_SPEC)
    assert set(artifacts) == {"cdc/policies_cdc", "cdc/premiums_cdc", "cdc/claims_cdc", "cdc/settlements_cdc"}
