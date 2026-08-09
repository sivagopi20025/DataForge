# Insurance scenario research

Common workflows: customers, agents, policies, premiums, claims, and settlements.

Common data failures: suspicious claims, duplicate claims, coverage exceeded, renewal failure, premium miscalculation, and delayed settlement.

Business-rule failures: claim amount above coverage, settlement above claim, premium mismatch, expired policy claim, and renewal date error.

Pipeline failures: duplicate claim retry, dropped premium batch, delayed settlement extract, and claim amount outlier.

Expected validations: policy FK integrity, claim coverage rule, premium/settlement reconciliation, date sequence, duplicate claim detection, and fraud-risk outlier checks.

References:

- SynthETIC insurance claim simulator — Actuarial research/open-source community — https://github.com/agi-lab/SynthETIC — reviewed 2026-07-11 — open-source synthetic simulator reference only — derived claim development/settlement dependency themes — no_copied_rows=true
- NAIC consumer insurance topics — National Association of Insurance Commissioners — https://content.naic.org/consumer.htm — reviewed 2026-07-11 — public information reference — derived policy/premium/claim/renewal concepts — no_copied_rows=true

Assumptions: renewal behavior is represented through current policy/premium fields.

Unresolved questions: future schema may need explicit renewal events.

