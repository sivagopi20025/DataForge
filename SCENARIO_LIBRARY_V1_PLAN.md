# DataForge Scenario Library V1 Plan

- Active scenarios: 760
- Rejected scenarios: 36
- Runtime executable scenarios unchanged: 50

## Count per domain
- banking: 80
- ecommerce: 80
- education: 65
- finance: 80
- healthcare: 80
- insurance: 75
- logistics: 75
- manufacturing: 75
- retail: 75
- telecommunications: 75

## Business-process distribution
- banking:accounts: 7
- banking:cards: 6
- banking:compliance: 6
- banking:customer_onboarding: 7
- banking:fees: 6
- banking:fraud: 6
- banking:kyc: 6
- banking:ledger: 6
- banking:loans: 6
- banking:payments: 6
- banking:reconciliation: 6
- banking:settlement: 6
- banking:transfers: 6
- ecommerce:cart: 5
- ecommerce:catalog: 5
- ecommerce:checkout: 5
- ecommerce:customer: 5
- ecommerce:fulfillment: 5
- ecommerce:inventory: 5
- ecommerce:marketplace_sellers: 5
- ecommerce:orders: 5
- ecommerce:payments: 5
- ecommerce:product_views: 5
- ecommerce:reconciliation: 5
- ecommerce:refunds: 5
- ecommerce:returns: 5
- ecommerce:reviews: 5
- ecommerce:search: 5
- ecommerce:shipping: 5
- education:admissions: 5
- education:assignments: 5
- education:attendance: 5
- education:courses: 5
- education:enrollment: 5
- education:exams: 5
- education:fees: 5
- education:grades: 5
- education:graduation: 5
- education:holds: 5
- education:online_learning: 5
- education:reconciliation: 5
- education:student_lifecycle: 5
- finance:compliance: 6
- finance:currency: 6
- finance:fees: 6
- finance:market_data: 7
- finance:orders: 6
- finance:portfolio: 6
- finance:positions: 6
- finance:pricing: 6
- finance:reconciliation: 6
- finance:risk: 6
- finance:settlement: 6
- finance:trading: 7
- finance:transactions: 6
- healthcare:care_coordination: 6
- healthcare:claims: 7
- healthcare:compliance: 6
- healthcare:diagnosis: 7
- healthcare:eligibility: 7
- healthcare:patient_registration: 7
- healthcare:payments: 7
- healthcare:pharmacy: 6
- healthcare:procedures: 7
- healthcare:provider_master: 7
- healthcare:reconciliation: 6
- healthcare:visits: 7
- insurance:claims: 6
- insurance:compliance: 6
- insurance:coverage: 6
- insurance:customer: 7
- insurance:deductible: 6
- insurance:fraud: 6
- insurance:policy_lifecycle: 7
- insurance:premium: 6
- insurance:reconciliation: 6
- insurance:renewal: 6
- insurance:settlement: 6
- insurance:underwriting: 7
- logistics:billing: 5
- logistics:carrier_management: 6
- logistics:cold_chain: 6
- logistics:customs: 6
- logistics:delivery: 6
- logistics:exceptions: 6
- logistics:gps: 6
- logistics:reconciliation: 5
- logistics:routing: 6
- logistics:shipment_creation: 6
- logistics:support: 5
- logistics:tracking: 6
- logistics:warehouse: 6
- manufacturing:capacity: 6
- manufacturing:downtime: 6
- manufacturing:inventory: 6
- manufacturing:machine_operations: 7
- manufacturing:maintenance: 6
- manufacturing:plant_operations: 7
- manufacturing:production_planning: 7
- manufacturing:quality: 6
- manufacturing:reconciliation: 6
- manufacturing:safety: 6
- manufacturing:suppliers: 6
- manufacturing:work_orders: 6
- retail:catalog: 6
- retail:customer: 6
- retail:data_quality_control: 5
- retail:fulfillment: 5
- retail:inventory: 5
- retail:order_management: 6
- retail:payments: 5
- retail:pricing: 6
- retail:promotions: 6
- retail:reconciliation: 5
- retail:refunds: 5
- retail:returns: 5
- retail:stores: 5
- retail:suppliers: 5
- telecommunications:billing: 6
- telecommunications:data_usage: 6
- telecommunications:fraud: 5
- telecommunications:network_outages: 6
- telecommunications:plans: 6
- telecommunications:reconciliation: 5
- telecommunications:roaming: 6
- telecommunications:sms_usage: 6
- telecommunications:streaming_operations: 5
- telecommunications:subscriber_lifecycle: 6
- telecommunications:support: 6
- telecommunications:tower_operations: 6
- telecommunications:voice_usage: 6

## Failure-category distribution
- temporal: 120
- sequence: 98
- aggregate_mismatch: 71
- cross_table_mismatch: 56
- threshold_violation: 56
- calculation: 51
- status_transition: 49
- retry: 43
- volume_anomaly: 43
- capacity: 31
- duplication: 28
- availability: 15
- boundary_violation: 15
- policy_violation: 14
- geographic: 14
- timeout: 14
- missing_data: 9
- data_format: 9
- distribution_anomaly: 7
- invalid_value: 5
- identity_mismatch: 5
- referential_integrity: 4
- fraud_anomaly: 3

## Tier distribution
- Tier A: 757
- Tier B: 3

## Ready-now scenarios
- Ready now count: 49
- Needs new table: 179
- Needs only/new columns: 274
- Needs new primitive: 617
- Needs new validator: 618

## Highest-leverage existing tables
- banking.customers: 25 scenarios
- insurance.claims: 24 scenarios
- insurance.policies: 21 scenarios
- logistics.shipments: 21 scenarios
- banking.payments: 20 scenarios
- healthcare.providers: 19 scenarios
- manufacturing.factories: 19 scenarios
- finance.transactions: 18 scenarios
- retail.categories: 18 scenarios
- healthcare.diagnoses: 17 scenarios
- healthcare.patients: 17 scenarios
- insurance.customers: 16 scenarios
- ecommerce.marketplace_customers: 15 scenarios
- healthcare.claims: 15 scenarios
- logistics.customers: 15 scenarios

## Highest-leverage proposed tables
- finance.trades: 10 scenarios
- finance.market_data: 9 scenarios
- banking.card_authorizations: 8 scenarios
- ecommerce.seller_payouts: 8 scenarios
- finance.risk_events: 8 scenarios
- finance.positions: 8 scenarios
- healthcare.prior_authorizations: 8 scenarios
- banking.ledger_entries: 7 scenarios
- ecommerce.product_views: 7 scenarios
- education.academic_standing_events: 7 scenarios
- education.fee_payments: 7 scenarios
- logistics.exception_alerts: 7 scenarios
- manufacturing.sensor_readings: 7 scenarios
- retail.refund_events: 7 scenarios
- insurance.claim_documents: 6 scenarios

## Highest-leverage proposed columns
- finance.trades.amount: 10 scenarios
- finance.trades.event_timestamp: 10 scenarios
- finance.trades.reason_code: 10 scenarios
- finance.trades.risk_event_id: 10 scenarios
- finance.trades.status: 10 scenarios
- finance.market_data.amount: 9 scenarios
- finance.market_data.event_timestamp: 9 scenarios
- finance.market_data.reason_code: 9 scenarios
- finance.market_data.risk_event_id: 9 scenarios
- finance.market_data.status: 9 scenarios
- banking.card_authorizations.card_authorization_id: 8 scenarios
- banking.card_authorizations.event_timestamp: 8 scenarios
- banking.card_authorizations.reason_code: 8 scenarios
- ecommerce.seller_payouts.amount: 8 scenarios
- ecommerce.seller_payouts.event_timestamp: 8 scenarios

## Primitive expansion recommendation
- value_below_threshold: 16 scenarios, 16 Tier A
- future_timestamp: 22 scenarios, 21 Tier A
- stale_timestamp: 27 scenarios, 27 Tier A
- timestamp_delay: 55 scenarios, 55 Tier A
- timestamp_out_of_order: 50 scenarios, 50 Tier A
- sequence_gap: 48 scenarios, 48 Tier A
- invalid_state_transition: 49 scenarios, 48 Tier A
- aggregate_mismatch: 71 scenarios, 71 Tier A
- cross_table_mismatch: 56 scenarios, 56 Tier A
- calculation_error: 48 scenarios, 48 Tier A
- capacity_exceeded: 27 scenarios, 27 Tier A
- volume_spike: 25 scenarios, 25 Tier A

## Validator expansion recommendation
- duplicate_key_validator: 39 scenarios, 39 Tier A
- threshold_validator: 28 scenarios, 28 Tier A
- temporal_order_validator: 22 scenarios, 21 Tier A
- sla_validator: 96 scenarios, 96 Tier A
- state_transition_validator: 49 scenarios, 48 Tier A
- aggregate_balance_validator: 71 scenarios, 71 Tier A
- cross_table_consistency_validator: 58 scenarios, 58 Tier A
- calculation_validator: 48 scenarios, 48 Tier A
- volume_anomaly_validator: 43 scenarios, 43 Tier A
- sequence_validator: 122 scenarios, 122 Tier A
- availability_validator: 15 scenarios, 15 Tier A
- capacity_validator: 27 scenarios, 27 Tier A

## Scenarios requiring custom logic
- Scenario-specific validator pattern count: 34
- Keep custom validators rare; prefer reusable validator patterns for Prompt 3.

## Recommended Prompt 3 implementation order
1. banking_cards_treasury_position_value_above_threshold_01
2. banking_customer_onboarding_customer_duplicate_transaction_03
3. banking_fees_payment_future_timestamp_04
4. banking_fees_payment_value_above_threshold_02
5. banking_kyc_customer_future_timestamp_05
6. banking_kyc_customer_negative_numeric_value_02
7. banking_kyc_customer_value_above_threshold_03
8. banking_loans_transfer_value_above_threshold_01
9. banking_settlement_transfer_settlement_delay_05
10. ecommerce_cart_cart_future_timestamp_02
11. ecommerce_inventory_product_listing_inventory_oversell_02
12. ecommerce_inventory_product_listing_negative_numeric_value_03
13. ecommerce_marketplace_sellers_seller_duplicate_transaction_01
14. education_grades_enrollment_grade_formula_error_01
15. education_grades_enrollment_grade_formula_error_04
16. finance_fees_transaction_future_timestamp_04
17. finance_fees_transaction_negative_numeric_value_01
18. finance_fees_transaction_value_above_threshold_02
19. finance_settlement_transaction_settlement_delay_05
20. healthcare_care_coordination_provider_duplicate_transaction_02
21. healthcare_claims_claim_coverage_limit_violation_01
22. healthcare_patient_registration_patient_schema_change_07
23. insurance_claims_claim_coverage_limit_violation_01
24. insurance_claims_claim_invalid_reference_03
25. insurance_fraud_claim_future_timestamp_01
26. insurance_policy_lifecycle_policie_duplicate_transaction_04
27. logistics_cold_chain_delivery_record_temperature_threshold_breach_01
28. logistics_cold_chain_delivery_record_temperature_threshold_breach_04
29. logistics_cold_chain_delivery_record_value_above_threshold_06
30. manufacturing_machine_operations_machine_schema_change_06

## Architectural risk
The active runtime still executes only the existing Python-defined 50 scenarios. Prompt 3 should add primitive and validator registries so specification-only scenarios can become executable without scenario_id if/elif branching.
