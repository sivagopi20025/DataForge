# DataForge SLM Scenario Router Plan

This plan prepares DataForge for a future small language model or deterministic
router that maps user intent to scenario configuration.

No LLM/SLM inference is implemented in this phase.

## Training artifacts

- `dataforge/training/scenario_knowledge.jsonl`
  - One row per active scenario.
  - Contains canonical scenario metadata, execution readiness, dependencies, and
    routing-relevant fields.

- `dataforge/training/scenario_instruction_seed.jsonl`
  - Five synthetic user-instruction variants per scenario.
  - Each row contains an expected structured router output.

- `dataforge/training/scenario_router_output.schema.json`
  - JSON Schema generated from `ScenarioRouterOutput`.
  - Defines the future router response contract.

## Router output contract

The future router should return:

- scenario id
- domain
- confidence
- execution mode
- record count
- output format
- realism profile
- severity
- failure primitive
- validator pattern
- selected tables and columns
- failure rate
- rationale
- missing capabilities

## Safety constraints

The router must not invent unsupported domains, tables, columns, primitives,
validators, or execution modes. If a matched scenario is specification-only, the
router should return it with `missing_capabilities` populated instead of claiming
it can run.

## Future phases

1. Add offline evaluation prompts and expected outputs.
2. Add negative examples for unsupported requests.
3. Add deterministic fallback matching for low-confidence model outputs.
4. Add per-domain router evaluations.
5. Add human-reviewed corrections from beta usage.
