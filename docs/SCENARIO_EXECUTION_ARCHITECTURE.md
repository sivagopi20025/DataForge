# DataForge Scenario Execution Architecture

DataForge now separates scenario specification from runtime execution.

The catalog can contain hundreds of enterprise scenarios, while the runtime
only executes scenarios whose tables, columns, primitives, validators, and
parameters are currently supported.

## Layers

1. **Scenario catalog**
   - Source: `dataforge/scenarios/catalog/scenario_library.yaml`
   - Contract: `MasterScenarioMetadata`
   - Purpose: business taxonomy, failure primitive, validator pattern, evidence,
     scoring, readiness, and execution status.

2. **Requirement resolver**
   - Source: `dataforge/scenarios/requirements.py`
   - Determines whether a scenario is executable now.
   - Reports missing tables, columns, primitives, validators, unsupported
     parameters, and custom-logic requirements.

3. **Primitive registry**
   - Source: `dataforge/scenarios/primitives.py`
   - Maps canonical and legacy primitive names to executable mutation functions
     where generic execution is safe.
   - Legacy reference primitives are preserved as aliases/adapters instead of
     deleting working reference implementations.

4. **Validator registry**
   - Source: `dataforge/scenarios/validator_registry.py`
   - Maps validator patterns to generic validators where possible.
   - Scenario-specific validators remain authoritative for the 10 deeply
     implemented reference scenarios.

5. **Generic executor**
   - Source: `dataforge/scenarios/generic_executor.py`
   - Executes only scenarios resolved as supported.
   - Flow: generate clean data, apply realism, execute primitive, run validator,
     return evidence and reconciliation.

## Execution statuses

- `executable`: generic primitive and validator are available now.
- `custom_reference`: deeply implemented reference scenario using custom logic.
- `specification_only`: valid catalog scenario, but runtime dependencies are not
  complete yet.
- `rejected`: excluded from the active catalog because scope, legality, data
  model fit, or product value is insufficient.

## Current reconciliation

The active catalog contains 760 scenarios. The runtime-capable subset contains
generic executable scenarios plus the custom reference scenarios. Specification
only scenarios are intentionally retained as roadmap/training inventory, not
presented as fully runnable workflows.

## Rule of thumb

If a scenario requires a new table, new column, unsupported primitive, unsupported
validator, or unsupported parameter, keep it `specification_only` until the
missing capability is implemented and tested.
