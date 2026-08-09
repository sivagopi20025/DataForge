from dataforge.domains.telecommunications.generators import TelecommunicationsGenerator
from dataforge.domains.telecommunications.schemas import TELECOMMUNICATIONS_SPEC
from dataforge.validation import relationship_report


def test_telecommunications_relationships_have_no_orphans():
    data = TelecommunicationsGenerator(150, seed=83).generate()
    report = relationship_report(data, TELECOMMUNICATIONS_SPEC)
    assert report["overall_status"] == "PASS"
    assert len(report["relationships"]) == 24


def test_telecommunications_relationship_validation_catches_orphan_cdr_subscription():
    data = TelecommunicationsGenerator(80, seed=84).generate()
    data["call_detail_records"][0]["subscription_id"] = 999999999
    report = relationship_report(data, TELECOMMUNICATIONS_SPEC)
    assert report["overall_status"] == "FAIL"
    assert any(
        item["child_table"] == "call_detail_records" and item["child_column"] == "subscription_id"
        for item in report["relationships"]
        if item["status"] == "FAIL"
    )
