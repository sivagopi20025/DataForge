from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dataforge.domains import DOMAIN_GENERATORS, DOMAIN_SPECS
from dataforge.realism import apply_realism
from dataforge.scenarios.catalog.models import MasterScenarioMetadata
from dataforge.scenarios.primitives import PRIMITIVE_REGISTRY, PrimitiveExecutionContext
from dataforge.scenarios.requirements import REQUIREMENT_RESOLVER
from dataforge.scenarios.schema_semantics import COLUMN_SEMANTIC_RESOLVER
from dataforge.scenarios.validator_registry import VALIDATOR_REGISTRY, ValidatorExecutionContext


@dataclass
class GenericScenarioExecutionResult:
    scenario_id: str
    execution_status: str
    primitive_result: dict[str, Any]
    validator_result: dict[str, Any]
    scenario_outcome: str
    requirement_resolution: dict[str, Any]


def execute_generic_scenario(
    scenario: MasterScenarioMetadata,
    *,
    records: int = 100,
    seed: int = 42,
    severity: str | None = None,
) -> GenericScenarioExecutionResult:
    resolution = REQUIREMENT_RESOLVER.resolve(scenario)
    if not resolution.execution_supported:
        raise ValueError(f"Scenario is not generically executable: {resolution.model_dump()}")

    spec = DOMAIN_SPECS[scenario.domain]
    generator = DOMAIN_GENERATORS[scenario.domain](records, seed, "bulk", 1)
    dataset = generator.generate()
    selected_tables = {table for table in scenario.related_tables if table in spec.schemas}
    dataset, _ = apply_realism(dataset, spec, profile="realistic", seed=seed, selected_tables=selected_tables or set(spec.schemas))

    parameters = COLUMN_SEMANTIC_RESOLVER.normalize_parameters(
        scenario.domain,
        scenario.primary_table,
        scenario.primitive_parameters,
    )
    parameters.setdefault("table", scenario.primary_table)
    parameters.setdefault("affected_rate_default", 0.03)
    primitive_result = PRIMITIVE_REGISTRY.execute(
        scenario.failure_primitive,
        PrimitiveExecutionContext(
            dataset=dataset,
            spec=spec,
            parameters=parameters,
            seed=seed,
            severity=severity or scenario.severity,
        ),
    )
    validator_parameters = COLUMN_SEMANTIC_RESOLVER.normalize_parameters(
        scenario.domain,
        scenario.primary_table,
        scenario.validator_parameters,
    )
    validator_parameters.setdefault("table", scenario.primary_table)
    if "columns" not in validator_parameters and scenario.required_columns:
        validator_parameters["columns"] = COLUMN_SEMANTIC_RESOLVER.normalize_parameters(
            scenario.domain,
            scenario.primary_table,
            {"columns": scenario.required_columns[:4]},
        )["columns"]
    validator_result = VALIDATOR_REGISTRY.validate(
        scenario.validator_pattern,
        ValidatorExecutionContext(
            dataset=primitive_result.dataset,
            spec=spec,
            parameters=validator_parameters,
            primitive_result=primitive_result,
            expected_count=primitive_result.actual_mutated_count,
            severity=severity or scenario.severity,
        ),
    )
    outcome = "PASS" if validator_result["status"] == "PASS" and validator_result["reconciliation_status"] == "PASS" else "FAIL"
    return GenericScenarioExecutionResult(
        scenario_id=scenario.scenario_id,
        execution_status="executable",
        primitive_result={
            "primitive_id": primitive_result.primitive_id,
            "selected_count": primitive_result.selected_count,
            "actual_mutated_count": primitive_result.actual_mutated_count,
            "affected_tables": primitive_result.affected_tables,
            "affected_entity_ids": primitive_result.affected_entity_ids[:100],
            "mutation_metadata": primitive_result.mutation_metadata,
            "warnings": primitive_result.warnings,
        },
        validator_result=validator_result,
        scenario_outcome=outcome,
        requirement_resolution=resolution.model_dump(),
    )
