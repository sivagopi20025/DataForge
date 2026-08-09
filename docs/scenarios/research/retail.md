# Retail scenario research

Common workflows: product catalog, promotion pricing, inventory snapshots, sales, payments, returns, purchase orders, and shipments.

Common data failures: duplicate orders/payments, inventory mismatch, invalid promotion pricing, late fulfillment, missing return/payment records, and malformed timestamps.

Business-rule failures: payment idempotency failure, sale amount not matching price/quantity/discount, negative stock, and shipment dates outside expected order windows.

Pipeline failures: duplicate batch loads, retry replay, stale inventory snapshots, late-arriving shipment events, and reconciliation mismatches.

Expected validations: primary-key uniqueness, foreign-key integrity, duplicate detection, amount reconciliation, inventory threshold checks, date sequence checks, and outlier checks.

References:

- dbt generic data tests — dbt Labs — https://docs.getdbt.com/docs/build/data-tests — reviewed 2026-07-11 — documentation reference only — derived unique/not-null/relationship/accepted-value validation patterns — no_copied_rows=true
- UCI Online Retail catalog — UCI Machine Learning Repository — https://archive.ics.uci.edu/ — reviewed 2026-07-11 — metadata reference only — derived retail order/product/customer/payment lifecycle patterns — no_copied_rows=true

Assumptions: synthetic retail scenarios model common enterprise testing risks, not official retail benchmarks.

Unresolved questions: whether beta users want separate fulfillment-carrier tables or current shipment tables are enough.

