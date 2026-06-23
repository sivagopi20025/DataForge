# DataForge Enterprise Dataset Generator

DataForge generates coherent domain datasets, injects known data-quality
failures, validates expected vs. actual results, and exports pipeline-ready
artifacts. Retail, Logistics, Healthcare, Finance, Insurance, and Banking now
run through the same shared framework.

Current version: `0.6.0`.

## Supported domains

- `retail`
- `logistics`
- `healthcare`
- `finance`
- `insurance`
- `banking`

Future domains should only need schemas, relationships, fixtures/generators,
business rules, and issue-column mappings.

## Quick start

Retail:

```bash
python3 retail_generator.py \
  --domain retail \
  --records 10000 \
  --load-type bulk \
  --output-format csv json \
  --dataset-name retail_sample
```

Logistics:

```bash
python3 retail_generator.py \
  --domain logistics \
  --records 10000 \
  --load-type bulk \
  --output-format csv json \
  --dataset-name logistics_sample
```

Healthcare:

```bash
python3 retail_generator.py \
  --domain healthcare \
  --records 10000 \
  --load-type bulk \
  --output-format csv json \
  --dataset-name healthcare_sample
```

Finance:

```bash
python3 retail_generator.py \
  --domain finance \
  --records 10000 \
  --load-type bulk \
  --output-format csv json \
  --dataset-name finance_sample
```

Insurance:

```bash
python3 retail_generator.py \
  --domain insurance \
  --records 10000 \
  --load-type bulk \
  --output-format csv json \
  --dataset-name insurance_sample
```

Banking:

```bash
python3 retail_generator.py \
  --domain banking \
  --records 10000 \
  --load-type bulk \
  --output-format csv json \
  --dataset-name banking_sample
```

`retail_generator.py` is kept as the compatibility entry point. If installed as
a package, the new script name is `dataforge`.

## Select generated files

Generate every table:

```bash
python3 retail_generator.py --domain logistics --tables all
```

Generate one table:

```bash
python3 retail_generator.py --domain logistics --tables shipments
```

Generate a selected collection:

```bash
python3 retail_generator.py \
  --domain logistics \
  --tables shipments tracking_events gps_events \
  --output-format csv json
```

Comma-separated table names are also accepted.

## Load types

| Mode | Output | Semantics |
|---|---|---|
| `bulk` | `bulk/<table>` | Complete independent snapshot |
| `incremental` | `incremental/day_1..3/<table>` | New, updated, and late-arriving records |
| `delta` | `delta/<table>_delta` | MERGE-oriented new, updated, and delete-marked records |
| `cdc` | `cdc/<table>_cdc` | INSERT/UPDATE/DELETE envelopes with before/after values |
| `event_stream` | `events/<event-name>` | Kafka/PubSub-style business event envelopes |

The old `--load-type event` alias still works and is normalized to
`event_stream`.

## Domains

Retail tables:

```text
categories, suppliers, stores, customers, products, employees, promotions,
inventory, sales, payments, returns, purchase_orders, shipments
```

Logistics tables:

```text
customers, warehouses, drivers, vehicles, shipments, delivery_records,
tracking_events, gps_events
```

Healthcare tables:

```text
patients, providers, visits, diagnoses, procedures, claims, payments
```

Finance tables:

```text
customers, accounts, transactions, cards, loans, payments
```

Insurance tables:

```text
customers, agents, policies, premiums, claims, settlements
```

Banking tables:

```text
customers, branches, deposit_accounts, payments, transfers,
treasury_positions, treasury_transactions
```

Healthcare represents provider-side patient visits, diagnosis/procedure coding,
claims, and payments. Business validations include DOB/age checks, ICD/CPT
checks, payment amount checks, claim/payment status checks, and relationship
checks across patient, provider, visit, claim, and payment chains.

Finance represents retail banking customers, accounts, transactions, cards,
loans, and payments. Business validations include account/customer/card/loan
relationship checks, savings balance checks, closed/frozen account transaction
checks, loan payment checks, status validation, and interest-rate validation.

Insurance represents policy and claims processing across customers, agents,
policies, premiums, claims, and settlements. Business validations include policy
lifecycle/status checks, claim coverage checks, settlement amount checks,
cancelled-policy premium checks, expired/cancelled policy claim checks, and
agent/customer relationship checks.

Banking represents core banking, payments, transfers, and treasury operations
across customers, branches, deposit accounts, payments, transfers, treasury
positions, and treasury transactions. Business validations include account,
payment, transfer, treasury, currency, lifecycle, and reconciliation checks.

Retail CDC currently emits `sales`. Logistics CDC emits `shipments`,
`delivery_records`, and `vehicles`. Healthcare CDC emits `patients`, `visits`,
`claims`, and `payments`. Finance CDC emits `accounts`, `transactions`, `cards`,
`loans`, and `payments`. Insurance CDC emits `policies`, `premiums`, `claims`,
and `settlements`. Banking CDC emits `deposit_accounts`, `payments`, `transfers`,
`treasury_positions`, and `treasury_transactions`. Event streams are
domain-defined.

## Issue injection

Use a profile:

```bash
python3 retail_generator.py \
  --domain banking \
  --tables payments transfers \
  --inject-failures true \
  --failure-profile medium \
  --output-format csv json
```

The shared issue engine supports:

- null values
- duplicate records
- datatype mismatch
- invalid dates
- negative values
- foreign-key breaks
- outliers
- missing records

Healthcare mappings make the shared injector produce useful healthcare defects,
including invalid ICD/CPT codes, negative claim/payment amounts, claim-without-
visit, payment-without-claim, payment greater than claim, and invalid status
values.

Finance mappings make the shared injector produce useful finance defects,
including negative transaction/loan/payment amounts, transaction-without-account,
card-without-customer, payment-without-loan, invalid interest rates, invalid
statuses, outliers, duplicate transaction IDs, and missing records.

Insurance mappings make the shared injector produce useful insurance defects,
including claim-without-policy, claim amount greater than coverage, settlement-
without-claim, settlement greater than claim, premium-without-policy, invalid
policy/claim statuses, duplicate IDs, outliers, and missing records.

Banking mappings make the shared injector produce useful banking defects,
including payment-without-account, transfer-without-source/destination account,
negative transfer amounts, negative treasury positions, duplicate IDs, invalid
payment/transfer/account statuses, currency mismatches, and missing records.

Failure injection follows `--tables`, so one selected file, selected files, and
all files behave consistently across CSV, JSON, and Parquet.

## Reports

Every run creates:

```text
output/
└── <dataset-name>/
    └── <dataset-name>_<UTC timestamp>/
        ├── bulk/ | incremental/ | delta/ | cdc/ | events/
        ├── metadata.json
        ├── quality_report.json
        ├── failure_report.json
        ├── relationship_report.json
        ├── reconciliation_report.json
        └── schema_report.json
```

`metadata.json` records artifact row counts, columns, and SHA-256 checksums.

Validation reports use a standard contract across every domain:

```text
run_id, domain, load_type, format, record_count, quality_score, status,
summary, issues, checks, generated_at
```

Quality scores are weighted from 0 to 100 across primary key, foreign key,
schema, business-rule, duplicate, and date validations.

Schema drift injection and validation support:

- `COLUMN_ADDED`
- `COLUMN_REMOVED`
- `COLUMN_RENAMED`
- `DATATYPE_CHANGED`
- `NULLABILITY_CHANGED`
- `COLUMN_ORDER_CHANGED`

## Backend foundation

Phase 1 backend lives under `backend/` and wraps the existing generation engine
with FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL configuration, repository
classes, and admin analytics APIs.

Start database services:

```bash
docker compose up -d
```

Run migrations:

```bash
alembic -c backend/alembic.ini upgrade head
```

Run the API:

```bash
uvicorn backend.app.main:app --reload
```

Key endpoints:

- `GET /health`
- `POST /api/v1/generate`
- `POST /api/v1/validate`
- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/admin/analytics/overview`
- `GET /api/v1/admin/analytics/domains`
- `GET /api/v1/admin/analytics/formats`
- `GET /api/v1/admin/analytics/load-types`
- `GET /api/v1/admin/analytics/quality/domains`
- `GET /api/v1/admin/analytics/quality/load-types`
- `GET /api/v1/admin/analytics/quality/trends`
- `GET /api/v1/admin/analytics/quality/lowest-runs`
- `GET /api/v1/admin/analytics/quality/highest-runs`

See [backend/README.md](backend/README.md) for backend-specific details.

## Architecture notes

The refactor keeps the package rooted at `dataforge/` and separates:

- `dataforge/domains/retail/` — Retail schemas, relationships, generator, rules.
- `dataforge/domains/logistics/` — Logistics schemas, relationships, generator, rules.
- `dataforge/domains/healthcare/` — Healthcare schemas, relationships, generator, fixtures, issue mappings, and rules.
- `dataforge/domains/finance/` — Finance schemas, relationships, generator, fixtures, issue mappings, fraud tags, and rules.
- `dataforge/domains/insurance/` — Insurance schemas, relationships, generator, fixtures, issue mappings, fraud tags, and rules.
- `dataforge/domains/banking/` — Banking schemas, relationships, generator, fixtures, issue mappings, fraud/reconciliation tags, and rules.
- `dataforge/audit.py` — shared audit, record hash, SCD2/time hierarchy enrichment.
- `dataforge/injector.py` — shared issue injection engine.
- `dataforge/modes.py` — shared bulk, incremental, delta, CDC, event stream builders.
- `dataforge/validation.py` — shared PK/FK/schema/date/numeric/business validation.
- `dataforge/exporter.py` — shared CSV, JSON, and Parquet export.

Migration from the Retail-only version:

- Old Retail imports still work: `from dataforge.generator import RetailGenerator`.
- Old `--load-type event` still works.
- Old table-selection and timestamped output behavior is unchanged.
- New code should prefer domain-specific imports under `dataforge.domains`.
