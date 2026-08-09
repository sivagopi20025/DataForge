# E-commerce Marketplace scenario research

Common workflows: marketplace customers, sellers, stores, categories, products, listings, carts, orders, order items, payments, shipments, returns, reviews, and promotions.

Common data failures: payment retry duplicates, cart abandonment mismatches, inventory oversell, refund failure, order status mismatch, shipment delay, and invalid return lifecycle.

Business-rule failures: successful payment missing for paid order, shipment before payment, return without delivered order, oversold listing quantity, and invalid order status.

Pipeline failures: duplicate payment webhook, missing refund batch, delayed shipment event, out-of-order order status, and cart/order funnel drop.

Expected validations: duplicate payment detection, order/payment/shipment sequence, inventory availability, refund reconciliation, status enum checks, and funnel consistency.

References:

- UCI Online Retail catalog — UCI Machine Learning Repository — https://archive.ics.uci.edu/ — reviewed 2026-07-11 — metadata reference only — derived order/payment/shipment/return lifecycle themes — no_copied_rows=true
- Stripe idempotency documentation — Stripe — https://docs.stripe.com/api/idempotent_requests — reviewed 2026-07-11 — API documentation reference — derived payment retry/idempotency scenario pattern — no_copied_rows=true

Assumptions: marketplace inventory uses product listing availability in the current schema.

Unresolved questions: future scenarios may need explicit webhook event tables.

