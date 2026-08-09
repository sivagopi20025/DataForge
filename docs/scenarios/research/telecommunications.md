# Telecommunications scenario research

Common workflows: customers, plans, subscriptions, SIMs, devices, towers, CDRs, SMS, data sessions, invoices, payments, outages, and support tickets.

Common data failures: tower congestion, network outages, SMS delays, billing mismatch, roaming charge error, late events, duplicate events, and missing events.

Business-rule failures: invoice total mismatch, tower outage without affected sessions, dropped call spikes, invalid event sequence, and roaming charges outside expected range.

Pipeline failures: streaming delay, out-of-order events, duplicate replay, lost partition data, and burst traffic.

Expected validations: invoice reconciliation, event-time sequence, 5G/4G usage profile checks, outage/session consistency, support-ticket lift, and rate/outlier checks.

References:

- Apache Kafka documentation — Apache Software Foundation — https://kafka.apache.org/documentation/ — reviewed 2026-07-11 — open-source documentation reference — derived duplicate/replay/late/out-of-order streaming patterns — no_copied_rows=true
- UCI public dataset catalog — UCI Machine Learning Repository — https://archive.ics.uci.edu/ — reviewed 2026-07-11 — metadata reference only — derived telecom usage/churn relationship themes — no_copied_rows=true

Assumptions: streaming scenarios remain metadata-driven and reuse existing stream simulation.

Unresolved questions: rural drop rates may later split into normal/degraded/stress states.

