from __future__ import annotations

from dataforge.scenarios.registry import all_scenarios, scenario_summary


def match_scenarios(text: str, *, limit: int = 5) -> list[dict]:
    """Deterministic keyword/alias matcher for future SLM handoff.

    This is intentionally simple and isolated: an LLM can later produce
    ScenarioRunConfig directly, while this fallback supports search UX.
    """

    query = text.strip().lower()
    if not query:
        return []
    tokens = [token for token in query.split() if token]
    scored = []
    for scenario in all_scenarios():
        haystack = " ".join([scenario.scenario_id, scenario.name, *scenario.tags, *scenario.aliases]).lower()
        score = sum(1 for token in tokens if token in haystack)
        if score:
            scored.append((score, scenario))
    scored.sort(key=lambda item: (-item[0], item[1].scenario_id))
    return [scenario_summary(scenario) | {"match_score": score} for score, scenario in scored[:limit]]
