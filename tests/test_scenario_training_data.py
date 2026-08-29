from __future__ import annotations

import json
from pathlib import Path

from dataforge.scenarios.catalog import expanded_scenario_items
from dataforge.training.router_schema import ScenarioRouterOutput
from dataforge.training.validation import validate_instruction_seed_file, validate_scenario_knowledge_file


TRAINING_DIR = Path("dataforge/training")


def test_scenario_knowledge_jsonl_matches_active_catalog() -> None:
    path = TRAINING_DIR / "scenario_knowledge.jsonl"
    result = validate_scenario_knowledge_file(path)
    assert result.errors == []
    assert result.row_count == len(expanded_scenario_items()) == 810


def test_instruction_seed_jsonl_has_five_valid_unique_prompts_per_scenario() -> None:
    path = TRAINING_DIR / "scenario_instruction_seed.jsonl"
    result = validate_instruction_seed_file(path)
    assert result.errors == []
    assert result.row_count == len(expanded_scenario_items()) * 5


def test_router_schema_accepts_training_expected_output_contract() -> None:
    with (TRAINING_DIR / "scenario_instruction_seed.jsonl").open(encoding="utf-8") as handle:
        row = json.loads(next(handle))
    parsed = ScenarioRouterOutput.model_validate(row["expected_output"])
    assert parsed.scenario_id
    assert parsed.domain
    assert 0 <= parsed.failure_rate <= 1


def test_router_json_schema_is_generated_from_pydantic_model() -> None:
    schema_path = TRAINING_DIR / "scenario_router_output.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["title"] == "ScenarioRouterOutput"
    assert "scenario_id" in schema["properties"]
    assert "failure_rate" in schema["properties"]
