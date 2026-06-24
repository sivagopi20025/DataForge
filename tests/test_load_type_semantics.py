from datetime import datetime

from dataforge.domains.retail.generators import RetailGenerator
from dataforge.modes import build_artifacts


def test_incremental_load_contains_late_arriving_events():
    data = RetailGenerator(120, seed=303, load_type="incremental").generate()
    artifacts = build_artifacts(data, "incremental", seed=303, selected_tables={"sales"})

    rows = [row for artifact_rows in artifacts.values() for row in artifact_rows]
    late_rows = [row for row in rows if row["change_type"] == "LATE_ARRIVING"]

    assert late_rows
    for row in late_rows:
        assert datetime.fromisoformat(row["source_ts"]) < datetime.fromisoformat(row["ingestion_ts"])
