# Banking scenario research

Common workflows: customers, branches, deposit accounts, payments, transfers, treasury positions, and treasury transactions.

Common data failures: duplicate transfers, ledger imbalance, missing settlement rows, fraud bursts, invalid/frozen account references, and out-of-sequence payment events.

Business-rule failures: transfer from invalid account, destination account mismatch, debit/credit imbalance, failed settlement, and suspicious high-value activity.

Pipeline failures: retry replay, duplicate CDC event, missed settlement batch, delayed posting, and reconciliation drift.

Expected validations: account FK integrity, duplicate transfer detection, amount reconciliation, ledger balance, account status rules, and suspicious outlier detection.

References:

- CFPB/FFIEC HMDA public data — Consumer Financial Protection Bureau / FFIEC — https://ffiec.cfpb.gov/data-publication/ — reviewed 2026-07-11 — government public-data reference only — derived financial lifecycle and reporting consistency patterns — no_copied_rows=true
- Nacha Rules overview — Nacha — https://www.nacha.org/rules — reviewed 2026-07-11 — standards reference only — derived transfer/settlement risk themes — no_copied_rows=true

Assumptions: scenarios are synthetic payment/transfer tests and are not regulatory compliance claims.

Unresolved questions: future schema may need explicit settlement ledger entries.

