from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .model import Dataset, DomainSpec


PRIMARY_TABLES: dict[str, str] = {
    "retail": "sales",
    "logistics": "shipments",
    "healthcare": "visits",
    "finance": "transactions",
    "insurance": "claims",
    "banking": "payments",
    "manufacturing": "work_orders",
    "telecommunications": "call_detail_records",
    "education": "enrollments",
    "ecommerce": "orders",
}


REFERENCE_PROFILES: dict[str, list[dict[str, Any]]] = {
    "retail": [
        {
            "dataset_name": "Online Retail / Online Retail II",
            "source_provider": "UCI Machine Learning Repository",
            "source_url": "https://archive.ics.uci.edu/",
            "license_status": "Public research dataset; verify original repository terms before direct use.",
            "date_reviewed": "2026-07-11",
            "fields_or_rules_derived": ["invoice-like transactions", "SKU/product hierarchy", "customer/order temporal patterns"],
            "no_copied_rows": True,
        },
        {
            "dataset_name": "Public retail/e-commerce product categorization references",
            "source_provider": "Open academic/public dataset catalogs",
            "source_url": "https://www.kaggle.com/datasets",
            "license_status": "Metadata reference only; no Kaggle rows or licensed data copied.",
            "date_reviewed": "2026-07-11",
            "fields_or_rules_derived": ["category mix", "price bands", "promotion/return patterns"],
            "no_copied_rows": True,
        },
    ],
    "banking": [
        {
            "dataset_name": "HMDA public mortgage/application data",
            "source_provider": "Consumer Financial Protection Bureau / FFIEC",
            "source_url": "https://ffiec.cfpb.gov/data-publication/",
            "license_status": "Government public data; metadata/rule reference only.",
            "date_reviewed": "2026-07-11",
            "fields_or_rules_derived": ["application status patterns", "institution/geography relationships", "risk segmentation ideas"],
            "no_copied_rows": True,
        }
    ],
    "healthcare": [
        {
            "dataset_name": "CMS DE-SynPUF synthetic public use files",
            "source_provider": "Centers for Medicare & Medicaid Services",
            "source_url": "https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-claims-synthetic-public-use-files",
            "license_status": "Synthetic public-use reference; no rows copied.",
            "date_reviewed": "2026-07-11",
            "fields_or_rules_derived": ["patient-claim-payment chain", "diagnosis/procedure coding patterns", "claim status rules"],
            "no_copied_rows": True,
        }
    ],
    "manufacturing": [
        {
            "dataset_name": "Turbofan Engine Degradation Simulation / manufacturing sensor references",
            "source_provider": "NASA Prognostics Center of Excellence / public manufacturing references",
            "source_url": "https://www.nasa.gov/",
            "license_status": "Reference metadata only; no rows copied.",
            "date_reviewed": "2026-07-11",
            "fields_or_rules_derived": ["machine sensor ranges", "maintenance/downtime event patterns", "quality defect patterns"],
            "no_copied_rows": True,
        }
    ],
    "ecommerce": [
        {
            "dataset_name": "Online retail and marketplace behavior references",
            "source_provider": "UCI/Kaggle/public marketplace dataset catalogs",
            "source_url": "https://archive.ics.uci.edu/",
            "license_status": "Metadata/rule reference only; no rows copied.",
            "date_reviewed": "2026-07-11",
            "fields_or_rules_derived": ["order/payment/shipment flow", "review ratings", "seller/product/category ratios"],
            "no_copied_rows": True,
        }
    ],
    "logistics": [
        {
            "dataset_name": "NYC TLC trip record / public transport movement references",
            "source_provider": "NYC Taxi & Limousine Commission",
            "source_url": "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page",
            "license_status": "Government open-data reference; no rows copied.",
            "date_reviewed": "2026-07-11",
            "fields_or_rules_derived": ["pickup/dropoff timing", "location movement patterns", "delay/out-of-order event ideas"],
            "no_copied_rows": True,
        }
    ],
    "finance": [
        {
            "dataset_name": "UCI financial/time-series public dataset catalog references",
            "source_provider": "UCI Machine Learning Repository",
            "source_url": "https://archive.ics.uci.edu/",
            "license_status": "Metadata/rule reference only; no rows copied.",
            "date_reviewed": "2026-07-11",
            "fields_or_rules_derived": ["transaction amounts", "instrument/account relationships", "reconciliation rules"],
            "no_copied_rows": True,
        }
    ],
    "insurance": [
        {
            "dataset_name": "Public insurance claim/fraud dataset catalog references",
            "source_provider": "Kaggle/UCI/open government dataset catalogs",
            "source_url": "https://www.kaggle.com/datasets",
            "license_status": "Metadata/rule reference only; no rows copied.",
            "date_reviewed": "2026-07-11",
            "fields_or_rules_derived": ["policy-claim-payment flow", "claim status lifecycle", "reserve/payment constraints"],
            "no_copied_rows": True,
        }
    ],
    "education": [
        {
            "dataset_name": "IPEDS / public education statistics references",
            "source_provider": "National Center for Education Statistics",
            "source_url": "https://nces.ed.gov/ipeds/",
            "license_status": "Government statistics reference; no rows copied.",
            "date_reviewed": "2026-07-11",
            "fields_or_rules_derived": ["student/course/enrollment relationships", "term patterns", "program/department categories"],
            "no_copied_rows": True,
        }
    ],
    "telecommunications": [
        {
            "dataset_name": "Telecom usage/churn public dataset catalog references",
            "source_provider": "UCI/Kaggle/public dataset catalogs",
            "source_url": "https://archive.ics.uci.edu/",
            "license_status": "Metadata/rule reference only; no rows copied.",
            "date_reviewed": "2026-07-11",
            "fields_or_rules_derived": ["call detail records", "tower/session/billing relationships", "usage burst patterns"],
            "no_copied_rows": True,
        }
    ],
}


@dataclass(frozen=True)
class CanonicalDomainMetadata:
    domain: str
    primary_transaction_table: str
    table_schemas: dict[str, dict[str, Any]]
    table_volume_ratios: dict[str, float]
    business_rules: list[str]
    realism_profiles: dict[str, dict[str, Any]]
    source_references: list[dict[str, Any]] = field(default_factory=list)


def empty_dataset(spec: DomainSpec, selected_tables: set[str] | None = None) -> Dataset:
    selected = selected_tables or set(spec.schemas)
    return {table: [] for table in spec.schemas if table in selected}


def column_order(spec: DomainSpec, table: str) -> list[str]:
    return list(spec.schemas[table].columns)


def canonical_metadata(spec: DomainSpec) -> CanonicalDomainMetadata:
    primary = PRIMARY_TABLES.get(spec.name, next(iter(spec.schemas)))
    table_schemas: dict[str, dict[str, Any]] = {}
    for table, schema in spec.schemas.items():
        fk_columns = {fk.column for fk in schema.foreign_keys}
        table_schemas[table] = {
            "primary_key": schema.primary_key,
            "columns": list(schema.columns),
            "foreign_keys": [
                {
                    "column": fk.column,
                    "parent_table": fk.parent_table,
                    "parent_column": fk.parent_column,
                    "nullable": fk.nullable,
                }
                for fk in schema.foreign_keys
            ],
            "nullability": {
                column: (column in fk_columns and any(fk.column == column and fk.nullable for fk in schema.foreign_keys))
                for column in schema.columns
            },
        }
    ratios = {table: 1.0 for table in spec.schemas}
    if primary in ratios:
        ratios[primary] = 1.0
    realism_profiles = {
        "basic": {"description": "Deterministic synthetic values with valid relationships and broad plausible categories."},
        "realistic": {"description": "Reference-informed distributions, ranges, status lifecycles, and temporal/geographic patterns."},
        "stress": {"description": "Larger ranges, edge-case category mixes, and high-cardinality relationship coverage."},
    }
    return CanonicalDomainMetadata(
        domain=spec.name,
        primary_transaction_table=primary,
        table_schemas=table_schemas,
        table_volume_ratios=ratios,
        business_rules=[getattr(rule, "__name__", "business_rule") for rule in spec.business_rules],
        realism_profiles=realism_profiles,
        source_references=REFERENCE_PROFILES.get(spec.name, []),
    )


def realism_report(spec: DomainSpec, *, profile: str, requested_records: int, actual_counts: dict[str, int]) -> dict[str, Any]:
    metadata = canonical_metadata(spec)
    return {
        "domain": spec.name,
        "realism_profile": profile,
        "requested_primary_record_count": requested_records,
        "primary_transaction_table": metadata.primary_transaction_table,
        "actual_row_counts": actual_counts,
        "table_volume_ratios": metadata.table_volume_ratios,
        "realism_profiles": metadata.realism_profiles,
        "source_references": metadata.source_references,
        "no_public_rows_copied": True,
        "notes": [
            "Reference datasets are used only for metadata, distributions, ranges, categories, and business-rule inspiration.",
            "Generated rows are deterministic synthetic data and do not copy public dataset rows.",
        ],
    }
