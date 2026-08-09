from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dataforge.domains import DOMAIN_SPECS
from dataforge.scenarios.catalog.models import ImplementationDependencies, MasterScenarioMetadata
from dataforge.scenarios.primitives import PRIMITIVE_REGISTRY, PrimitiveRegistry
from dataforge.scenarios.schema_semantics import COLUMN_SEMANTIC_RESOLVER
from dataforge.scenarios.validator_registry import VALIDATOR_REGISTRY, ValidatorRegistry


@dataclass
class RequirementResolution:
    scenario_id: str
    execution_supported: bool
    missing_tables: list[str] = field(default_factory=list)
    missing_columns: list[str] = field(default_factory=list)
    missing_primitives: list[str] = field(default_factory=list)
    missing_validators: list[str] = field(default_factory=list)
    unsupported_parameters: list[str] = field(default_factory=list)
    custom_logic_required: bool = False

    @property
    def dependencies(self) -> ImplementationDependencies:
        return ImplementationDependencies(
            tables=self.missing_tables,
            columns=self.missing_columns,
            primitives=self.missing_primitives,
            validators=self.missing_validators,
            unsupported_parameters=self.unsupported_parameters,
            custom_logic=self.custom_logic_required,
        )

    def readiness(self) -> str:
        schema = bool(self.missing_tables or self.missing_columns)
        primitive = bool(self.missing_primitives)
        validator = bool(self.missing_validators)
        if self.custom_logic_required:
            return "needs_custom_logic"
        if not (schema or primitive or validator or self.unsupported_parameters):
            return "ready_now"
        if schema and primitive and validator:
            return "needs_schema_primitive_validator"
        if schema and primitive:
            return "needs_schema_and_primitive"
        if schema and validator:
            return "needs_schema_and_validator"
        if primitive and validator:
            return "needs_primitive_and_validator"
        if self.missing_tables:
            return "needs_table"
        if self.missing_columns:
            return "needs_columns"
        if primitive:
            return "needs_primitive_implementation"
        if validator:
            return "needs_validator_implementation"
        return "needs_primitive_parameter_support"

    def model_dump(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "execution_supported": self.execution_supported,
            "missing_tables": self.missing_tables,
            "missing_columns": self.missing_columns,
            "missing_primitives": self.missing_primitives,
            "missing_validators": self.missing_validators,
            "unsupported_parameters": self.unsupported_parameters,
            "custom_logic_required": self.custom_logic_required,
            "implementation_readiness": self.readiness(),
        }


class ScenarioRequirementResolver:
    def __init__(self, primitive_registry: PrimitiveRegistry = PRIMITIVE_REGISTRY, validator_registry: ValidatorRegistry = VALIDATOR_REGISTRY) -> None:
        self.primitive_registry = primitive_registry
        self.validator_registry = validator_registry

    def resolve(self, scenario: MasterScenarioMetadata) -> RequirementResolution:
        spec = DOMAIN_SPECS.get(scenario.domain)
        if not spec:
            return RequirementResolution(scenario.scenario_id, False, missing_tables=[scenario.primary_table])
        missing_tables = sorted({table for table in [scenario.primary_table, *scenario.related_tables] if table not in spec.schemas})
        existing_tables = [table for table in [scenario.primary_table, *scenario.related_tables] if table in spec.schemas]
        missing_columns = COLUMN_SEMANTIC_RESOLVER.missing_columns(
            scenario.domain,
            existing_tables or [scenario.primary_table],
            scenario.required_columns,
        )

        missing_primitives: list[str] = []
        try:
            primitive = self.primitive_registry.get(scenario.failure_primitive)
            if primitive.primitive_id not in self.primitive_registry.runtime_implemented():
                missing_primitives.append(primitive.primitive_id)
        except KeyError:
            missing_primitives.append(scenario.failure_primitive)

        missing_validators: list[str] = []
        try:
            validator = self.validator_registry.get(scenario.validator_pattern)
            if validator.validator_pattern_id not in self.validator_registry.runtime_implemented():
                missing_validators.append(validator.validator_pattern_id)
        except KeyError:
            missing_validators.append(scenario.validator_pattern)

        unsupported_parameters = self._unsupported_parameters(scenario)
        custom_logic_required = scenario.validator_pattern == "scenario_specific_validator" and scenario.status != "reference_implemented"
        supported = not (missing_tables or missing_columns or missing_primitives or missing_validators or unsupported_parameters or custom_logic_required)
        return RequirementResolution(
            scenario_id=scenario.scenario_id,
            execution_supported=supported,
            missing_tables=missing_tables,
            missing_columns=missing_columns,
            missing_primitives=missing_primitives,
            missing_validators=missing_validators,
            unsupported_parameters=unsupported_parameters,
            custom_logic_required=custom_logic_required,
        )

    def _unsupported_parameters(self, scenario: MasterScenarioMetadata) -> list[str]:
        allowed = {
            "table",
            "primary_table",
            "id_column",
            "column",
            "columns",
            "affected_rate",
            "affected_rate_default",
            "selector",
            "threshold",
            "canonicalized_from",
            "legacy_runtime_primitive",
        }
        return sorted(key for key in scenario.primitive_parameters if key not in allowed)


REQUIREMENT_RESOLVER = ScenarioRequirementResolver()
