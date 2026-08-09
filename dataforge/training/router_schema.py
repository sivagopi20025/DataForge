from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ScenarioRouterOutput(BaseModel):
    """Structured target emitted by a future scenario-router SLM/LLM.

    The router should select a scenario from the catalog and return normalized
    execution intent. It must not invent domains, primitives, validators, or
    unsupported execution modes.
    """

    scenario_id: str = Field(description="Canonical DataForge scenario identifier.")
    domain: str = Field(description="Canonical DataForge domain name.")
    confidence: float = Field(ge=0, le=1, description="Router confidence for this scenario match.")
    execution_mode: Literal["batch", "streaming", "specification_only"] = "batch"
    record_count: int = Field(default=1000, ge=0, le=500000)
    output_format: Literal["csv", "json", "parquet", "database"] = "csv"
    realism_profile: str = "realistic"
    severity: Literal["low", "medium", "high", "critical", "stress"] = "medium"
    failure_primitive: str
    validator_pattern: str
    selected_tables: list[str] = Field(default_factory=list)
    selected_columns: list[str] = Field(default_factory=list)
    failure_rate: float = Field(default=0.03, ge=0, le=1)
    rationale: str = Field(description="Short reason why this scenario matches the user request.")
    missing_capabilities: list[str] = Field(
        default_factory=list,
        description="Required primitives, validators, tables, columns, or parameters not currently executable.",
    )
