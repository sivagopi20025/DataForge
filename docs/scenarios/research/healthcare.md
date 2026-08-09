# Healthcare scenario research

Common workflows: patients, providers, visits, diagnoses, procedures, claims, and payments.

Common data failures: ghost providers, duplicate claims, missing diagnoses, invalid procedure codes, late approvals, and payment/claim mismatch.

Business-rule failures: claim without valid visit/provider/patient, procedure incompatible with diagnosis, payment exceeding claim, and invalid claim lifecycle sequence.

Pipeline failures: claim retry duplication, delayed approval batch, dropped diagnosis extract, and invalid code mapping.

Expected validations: FK integrity, ICD/CPT validity, diagnosis/procedure compatibility, claim lifecycle, payment amount, and date sequence checks.

References:

- CMS DE-SynPUF — Centers for Medicare & Medicaid Services — https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-claims-synthetic-public-use-files — reviewed 2026-07-11 — synthetic public-use reference only — derived provider/claim/payment relationship patterns — no_copied_rows=true
- ICD-10-CM codes — CMS/NCHS — https://www.cms.gov/medicare/coding-billing/icd-10-codes — reviewed 2026-07-11 — coding documentation reference — derived diagnosis/procedure validation themes — no_copied_rows=true

Assumptions: generated values are synthetic provider-side testing records, not clinical guidance.

Unresolved questions: future scenarios may need payer/plan tables.

