from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dataforge.scenarios.catalog import expanded_scenario_items
from dataforge.training.router_schema import ScenarioRouterOutput


TRAINING_DIR = Path(__file__).resolve().parent


def _dump_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def build_scenario_knowledge_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario in expanded_scenario_items():
        rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "scenario_name": scenario.scenario_name,
                "domain": scenario.domain,
                "business_process": scenario.business_process,
                "entity": scenario.entity,
                "description": scenario.description,
                "failure_category": scenario.failure_category,
                "failure_primitive": scenario.failure_primitive,
                "primitive_parameters": scenario.primitive_parameters,
                "primary_table": scenario.primary_table,
                "related_tables": scenario.related_tables,
                "required_columns": scenario.required_columns,
                "business_rule": scenario.business_rule,
                "mutation_strategy": scenario.mutation_strategy,
                "validator": scenario.validator,
                "validator_pattern": scenario.validator_pattern,
                "validator_parameters": scenario.validator_parameters,
                "expected_evidence": scenario.expected_evidence,
                "severity": scenario.severity,
                "realism": scenario.realism,
                "difficulty": scenario.difficulty,
                "tags": scenario.tags,
                "score": scenario.score.model_dump() if scenario.score else None,
                "implementation_readiness": scenario.implementation_readiness,
                "implementation_dependencies": scenario.implementation_dependencies.model_dump(),
                "execution_status": scenario.execution_status,
                "table_support_status": scenario.table_support_status,
                "training_value": scenario.training_value,
            }
        )
    return rows


def _expected_output(scenario_id: str) -> dict[str, Any]:
    scenario = next(item for item in expanded_scenario_items() if item.scenario_id == scenario_id)
    return ScenarioRouterOutput(
        scenario_id=scenario.scenario_id,
        domain=scenario.domain,
        confidence=0.91,
        execution_mode="streaming" if scenario.business_process == "streaming_operations" else "batch",
        record_count=1000,
        output_format="json" if scenario.business_process == "streaming_operations" else "csv",
        realism_profile=scenario.realism,
        severity=scenario.severity,
        failure_primitive=scenario.failure_primitive,
        validator_pattern=scenario.validator_pattern,
        selected_tables=scenario.related_tables,
        selected_columns=scenario.required_columns,
        failure_rate=float(scenario.primitive_parameters.get("affected_rate_default", 0.03)),
        rationale=f"The request maps to {scenario.domain} {scenario.failure_category} in {scenario.business_process}.",
        missing_capabilities=[
            *scenario.implementation_dependencies.tables,
            *scenario.implementation_dependencies.columns,
            *scenario.implementation_dependencies.primitives,
            *scenario.implementation_dependencies.validators,
            *scenario.implementation_dependencies.unsupported_parameters,
        ],
    ).model_dump()


def build_instruction_seed_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    templates = (
        "Scenario {scenario_id}: create a {domain} scenario for {scenario_name} using {severity} severity.",
        "Scenario {scenario_id}: I need test data where {description}",
        "Scenario {scenario_id}: generate {domain} {primary_table} data with {failure_category} failures and validate with {validator_pattern}.",
        "Scenario {scenario_id}: build a {realism} profile scenario for {business_process}: {business_rule}",
        "Scenario {scenario_id}: route this request to the scenario that checks {failure_primitive} on {primary_table}.",
    )
    for scenario in expanded_scenario_items():
        expected_output = _expected_output(scenario.scenario_id)
        values = scenario.model_dump()
        for variant, template in enumerate(templates, 1):
            rows.append(
                {
                    "instruction_id": f"{scenario.scenario_id}_seed_{variant:02d}",
                    "instruction": template.format(**values),
                    "expected_output": expected_output,
                    "source": "synthetic_router_seed",
                    "negative_example": False,
                }
            )
    return rows


def build_training_artifacts(directory: Path = TRAINING_DIR) -> dict[str, int]:
    directory.mkdir(parents=True, exist_ok=True)
    knowledge_rows = build_scenario_knowledge_rows()
    instruction_rows = build_instruction_seed_rows()
    _dump_jsonl(directory / "scenario_knowledge.jsonl", knowledge_rows)
    _dump_jsonl(directory / "scenario_instruction_seed.jsonl", instruction_rows)
    (directory / "scenario_router_output.schema.json").write_text(
        json.dumps(ScenarioRouterOutput.model_json_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "scenario_knowledge_rows": len(knowledge_rows),
        "scenario_instruction_seed_rows": len(instruction_rows),
    }


if __name__ == "__main__":
    print(json.dumps(build_training_artifacts(), indent=2))
