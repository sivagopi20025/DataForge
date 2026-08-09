# Manufacturing scenario research

Common workflows: factories, production lines, machines, products, work orders, batches, quality checks, defects, maintenance, employees, and inventory.

Common data failures: defect spikes, downtime spikes, missing quality gates, capacity overflow, delayed maintenance, sensor outliers, and late batch status events.

Business-rule failures: produced quantity above line capacity, missing inspection for completed batch, maintenance after failure, and rejected quantity mismatch.

Pipeline failures: sensor burst, delayed maintenance extract, dropped quality rows, duplicate production batch, and replayed machine events.

Expected validations: machine/line FK integrity, quantity reconciliation, downtime and defect outliers, temporal sequence, and missing quality check detection.

References:

- NASA Prognostics Center of Excellence — NASA — https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/ — reviewed 2026-07-11 — reference metadata only — derived degradation/downtime/sensor failure themes — no_copied_rows=true
- ISA-95 overview — ISA — https://www.isa.org/standards-and-publications/isa-standards/isa-95-standard — reviewed 2026-07-11 — standards reference only — derived manufacturing operations categories — no_copied_rows=true

Assumptions: DataForge uses current schema fields to represent manufacturing operational tests.

Unresolved questions: future beta users may request explicit sensor readings.

