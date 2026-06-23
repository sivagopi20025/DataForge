# DataForge Release Notes

## 0.6.0

- Added standard `ValidationReport` contract across all domains.
- Added weighted validation quality scoring from 0 to 100.
- Added schema drift injection support:
  - `COLUMN_ADDED`
  - `COLUMN_REMOVED`
  - `COLUMN_RENAMED`
  - `DATATYPE_CHANGED`
  - `NULLABILITY_CHANGED`
  - `COLUMN_ORDER_CHANGED`
- Added schema drift detection in validation reports.
- Added `quality_score` persistence to `validation_results`.
- Added analytics for average quality score, quality by domain, quality by load type, score trends, and ranked quality runs.
- Standardized Retail and Logistics folder structures with lightweight metadata modules.
- Confirmed database scope remains limited to Phase 1 backend tables.

## 0.5.0

- Added Banking domain.
- Added Insurance domain.
- Expanded test coverage across domains, CDC, event streams, issue injection, and performance checks.

## 0.3.0

- Added FastAPI backend foundation.
- Added SQLAlchemy models, repositories, Alembic, Docker Compose, and admin analytics APIs.
