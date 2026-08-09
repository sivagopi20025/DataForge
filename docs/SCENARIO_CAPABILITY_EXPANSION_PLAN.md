# DataForge Scenario Capability Expansion Plan

Prompt 4 expands executable scenario coverage by implementing reusable
capabilities, not one-off scenario branches.

## Leverage formula

`leverage_score = total_scenarios + tier_a_scenarios*3 + domains_reused*5 + business_processes_reused*2 - implementation_complexity*3`

The full machine-readable report is generated at:

`dataforge/scenarios/catalog/capability_leverage_report.yaml`

## Baseline

- Registered active scenarios: 760
- Generic executable before Batch 1: 70
- Custom reference executable before Batch 1: 10
- Runtime-capable before Batch 1: 80
- Specification-only before Batch 1: 680

## Batch 1 implemented

Name: `sequence_and_legacy_alias_unlock`

Implemented:

- Primitive: `timestamp_out_of_order`
- Primitive: `sequence_gap`
- Primitive: `duplicate_event`
- Validator: `sequence_validator`
- Parameter support: `legacy_runtime_primitive`

Schema expansion:

- No tables added
- No columns added

Why this batch:

- It unlocks broad cross-domain runtime coverage with low complexity.
- It requires no schema expansion.
- It validates the architecture’s generic primitive/validator scaling model.
- It also unblocks already-canonicalized legacy scenarios that only retained the
  old primitive name as metadata.

## After Batch 1

- Generic executable scenarios: 141
- Custom reference executable scenarios: 10
- Runtime-capable scenarios: 151
- Specification-only scenarios remaining: 609
- Newly executable scenarios: 71

## Batch 2 implemented

Name: `cross_table_and_aggregate_reconciliation`

Implemented capabilities:

- `cross_table_mismatch`
- `aggregate_mismatch`
- `cross_table_consistency_validator`
- `aggregate_balance_validator`

Schema expansion:

- No tables added
- No columns added

Outcome:

- Generic executable scenarios: 169
- Custom reference executable scenarios: 10
- Runtime-capable scenarios: 179
- Specification-only scenarios remaining: 581
- Newly executable scenarios from Batch 2: 28

Reasoning:

`cross_table_mismatch` unlocked 28 scenarios without schema expansion. `aggregate_mismatch`
and `aggregate_balance_validator` are runtime implemented and tested, but aggregate catalog
scenarios still require schema semantics such as domain-native expected/actual values or
grouping keys before they should be promoted.

## Batch 3 implemented

Name: `state_sla_and_volume_anomaly`

Implemented capabilities:

- `invalid_state_transition`
- `stale_timestamp`
- `timeout_violation`
- `volume_spike`
- `volume_drop`
- `state_transition_validator`
- `sla_validator`
- `volume_anomaly_validator`

Potential schema additions:

- None in Batch 3

Metadata added:

- `dataforge/scenarios/catalog/state_machines.yaml`
- `dataforge/scenarios/catalog/sla_policies.yaml`

Outcome:

- Generic executable scenarios: 254
- Custom reference executable scenarios: 10
- Runtime-capable scenarios: 264
- Specification-only scenarios remaining: 496
- Newly executable scenarios from Batch 3: 85

Reasoning:

Batch 3 unlocked state transition, SLA, stale timestamp, timeout, and volume anomaly
scenarios across all 10 domains without schema expansion. Validators inspect actual
generated rows against primitive-created baseline records.

## Batch 4 recommendation

Name: `threshold_policy_geo_identity`

Recommended capabilities:

- `value_below_threshold`
- `policy_violation`
- `availability_failure`
- `geographic_jump`
- `retry_burst`
- `policy_validator`
- `availability_validator`
- `geographic_validator`
- `reconciliation_validator`

Reason:

After Batch 3, these are the next highest-leverage primitive/validator blockers
that can likely be addressed without broad table expansion.

## Later schema-focused recommendation

Name: `aggregate_schema_completion`

Recommended capabilities:

- domain-native expected/actual reconciliation columns
- group keys for aggregate scenarios
- aggregate scenario metadata normalization

Potential schema additions:

- `expected_amount`
- `actual_amount`
- `reconciliation_group_id`

Reason:

Aggregate runtime is now available, but schema additions should be deliberate
and domain-native rather than globally adding generic fields everywhere.

## Remaining architecture risks

- Aggregate and cross-table validators must avoid “metadata-only PASS” behavior.
- Schema expansion should be driven by scenario reuse, not single scenario needs.
- Some policy/regulatory scenarios may still require custom logic after generic
  primitive composition is exhausted.
