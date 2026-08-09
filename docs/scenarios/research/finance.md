# Finance scenario research

Common workflows: customers, accounts, transactions, cards, loans, and payments.

Common data failures: month-end spikes, duplicate trades/transactions, currency conversion errors, settlement delays, fee miscalculation, and risk outliers.

Business-rule failures: amount/fee mismatch, invalid settlement timing, duplicated trade reference, failed account status rule, and suspicious size/volatility.

Pipeline failures: month-end batch pressure, duplicate CDC transaction, delayed settlement file, and schema/type mismatch in amount fields.

Expected validations: duplicate transaction detection, amount/outlier checks, date sequence, account FK integrity, fee/reconciliation checks, and datatype checks.

References:

- SEC EDGAR — U.S. Securities and Exchange Commission — https://www.sec.gov/edgar — reviewed 2026-07-11 — government public-data reference only — derived financial event and reporting lifecycle themes — no_copied_rows=true
- ISO 20022 overview — ISO — https://www.iso20022.org/ — reviewed 2026-07-11 — standards metadata reference only — derived settlement/message/reconciliation concepts — no_copied_rows=true

Assumptions: scenarios use current transaction fields; asset/security-level detail can be added later.

Unresolved questions: future finance schemas may need explicit trade, position, fee, and FX tables.

