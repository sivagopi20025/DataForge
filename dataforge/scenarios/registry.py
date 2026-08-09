from __future__ import annotations

from functools import lru_cache
from typing import Iterable

from dataforge.scenarios.domains import banking, ecommerce, education, finance, healthcare, insurance, logistics, manufacturing, retail, telecommunications
from dataforge.scenarios.models import ScenarioDefinition


DOMAIN_MODULES = (
    retail,
    logistics,
    healthcare,
    finance,
    insurance,
    banking,
    manufacturing,
    telecommunications,
    education,
    ecommerce,
)


@lru_cache(maxsize=1)
def all_scenarios() -> tuple[ScenarioDefinition, ...]:
    scenarios: list[ScenarioDefinition] = []
    for module in DOMAIN_MODULES:
        scenarios.extend(module.SCENARIOS)
    return tuple(scenarios)


@lru_cache(maxsize=1)
def scenario_map() -> dict[str, ScenarioDefinition]:
    return {scenario.scenario_id: scenario for scenario in all_scenarios()}


def get_scenario(scenario_id: str) -> ScenarioDefinition:
    try:
        return scenario_map()[scenario_id]
    except KeyError as error:
        raise ValueError(f"Unknown scenario_id: {scenario_id}") from error


def find_scenarios(
    *,
    domain: str | None = None,
    category: str | None = None,
    mode: str | None = None,
    profile: str | None = None,
    severity: str | None = None,
    tag: str | None = None,
    keyword: str | None = None,
) -> list[ScenarioDefinition]:
    results: Iterable[ScenarioDefinition] = all_scenarios()
    if domain:
        results = [scenario for scenario in results if scenario.domain == domain]
    if category:
        results = [scenario for scenario in results if scenario.category == category]
    if mode:
        results = [scenario for scenario in results if mode in scenario.supported_modes or "both" in scenario.supported_modes]
    if profile:
        results = [scenario for scenario in results if profile in scenario.recommended_realism_profiles]
    if severity:
        results = [scenario for scenario in results if severity in scenario.severity_levels]
    if tag:
        normalized = tag.lower()
        results = [scenario for scenario in results if normalized in {item.lower() for item in scenario.tags}]
    if keyword:
        needle = keyword.lower()
        results = [
            scenario
            for scenario in results
            if needle in " ".join(
                [
                    scenario.scenario_id,
                    scenario.name,
                    scenario.short_description,
                    scenario.business_problem,
                    scenario.technical_problem,
                    *scenario.tags,
                    *scenario.aliases,
                ]
            ).lower()
        ]
    return list(results)


def scenario_summary(scenario: ScenarioDefinition) -> dict:
    return {
        "scenario_id": scenario.scenario_id,
        "version": scenario.version,
        "name": scenario.name,
        "domain": scenario.domain,
        "category": scenario.category,
        "subcategory": scenario.subcategory,
        "short_description": scenario.short_description,
        "supported_modes": scenario.supported_modes,
        "default_mode": scenario.default_mode,
        "default_realism_profile": scenario.default_realism_profile,
        "default_record_count": scenario.default_record_count,
        "default_severity": scenario.default_severity,
        "tags": scenario.tags,
    }

