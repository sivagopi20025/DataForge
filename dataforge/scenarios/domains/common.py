from __future__ import annotations

from typing import Any

from dataforge.canonical import PRIMARY_TABLES
from dataforge.scenarios.models import FailureSpecification, ScenarioDefinition, ScenarioReference, ScenarioVariation

REFERENCE_SETS: dict[str, list[ScenarioReference]] = {
    "retail": [
        ScenarioReference(reference_name="dbt generic data tests", publisher="dbt Labs", url="https://docs.getdbt.com/docs/build/data-tests", date_reviewed="2026-07-11", license_status_note="Documentation reference only.", derived_rule="Unique, not-null, relationship, and accepted-value checks are common data quality validations."),
        ScenarioReference(reference_name="UCI Online Retail", publisher="UCI Machine Learning Repository", url="https://archive.ics.uci.edu/", date_reviewed="2026-07-11", license_status_note="Metadata reference only; no rows copied.", derived_rule="Retail order, customer, product, and return/payment workflows."),
    ],
    "banking": [
        ScenarioReference(reference_name="CFPB HMDA public data", publisher="Consumer Financial Protection Bureau", url="https://ffiec.cfpb.gov/data-publication/", date_reviewed="2026-07-11", license_status_note="Government public-data reference; no rows copied.", derived_rule="Financial application/account lifecycle and validation patterns."),
        ScenarioReference(reference_name="ACH risk management rules overview", publisher="Nacha", url="https://www.nacha.org/rules", date_reviewed="2026-07-11", license_status_note="Standards reference; no rule text copied.", derived_rule="Duplicate transfer and settlement timing scenarios."),
    ],
    "healthcare": [
        ScenarioReference(reference_name="CMS DE-SynPUF", publisher="Centers for Medicare & Medicaid Services", url="https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-claims-synthetic-public-use-files", date_reviewed="2026-07-11", license_status_note="Synthetic public-use reference; no rows copied.", derived_rule="Patient, provider, claim, and payment relationship patterns."),
        ScenarioReference(reference_name="ICD-10-CM official coding guidelines", publisher="CMS/NCHS", url="https://www.cms.gov/medicare/coding-billing/icd-10-codes", date_reviewed="2026-07-11", license_status_note="Coding documentation reference.", derived_rule="Diagnosis/procedure compatibility validation scenarios."),
    ],
    "manufacturing": [
        ScenarioReference(reference_name="NASA Prognostics Center of Excellence", publisher="NASA", url="https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/", date_reviewed="2026-07-11", license_status_note="Reference metadata only; no rows copied.", derived_rule="Machine degradation, downtime, sensor, and maintenance patterns."),
        ScenarioReference(reference_name="ISA-95 manufacturing operations model", publisher="International Society of Automation", url="https://www.isa.org/standards-and-publications/isa-standards/isa-95-standard", date_reviewed="2026-07-11", license_status_note="Standards reference; no standard text copied.", derived_rule="Production, quality, equipment, and maintenance workflow categories."),
    ],
    "telecommunications": [
        ScenarioReference(reference_name="Apache Kafka documentation", publisher="Apache Software Foundation", url="https://kafka.apache.org/documentation/", date_reviewed="2026-07-11", license_status_note="Open-source documentation reference.", derived_rule="Streaming duplicate, late, out-of-order, replay, and partitioned-event behavior."),
        ScenarioReference(reference_name="Telecom churn/usage public data catalogs", publisher="UCI/Kaggle catalogs", url="https://archive.ics.uci.edu/", date_reviewed="2026-07-11", license_status_note="Metadata reference only; no rows copied.", derived_rule="Call, SMS, data-session, tower, billing, and support-ticket patterns."),
    ],
    "logistics": [
        ScenarioReference(reference_name="NYC TLC trip record data", publisher="NYC Taxi & Limousine Commission", url="https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page", date_reviewed="2026-07-11", license_status_note="Government open-data reference; no rows copied.", derived_rule="Movement, pickup/dropoff, location, and delay-event patterns."),
        ScenarioReference(reference_name="Apache Flink event-time documentation", publisher="Apache Software Foundation", url="https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/time/", date_reviewed="2026-07-11", license_status_note="Open-source documentation reference.", derived_rule="Late, out-of-order, and event-time validation patterns."),
    ],
    "finance": [
        ScenarioReference(reference_name="SEC EDGAR data", publisher="U.S. Securities and Exchange Commission", url="https://www.sec.gov/edgar", date_reviewed="2026-07-11", license_status_note="Government public-data reference; no rows copied.", derived_rule="Financial instrument, filing, timing, and reconciliation concepts."),
        ScenarioReference(reference_name="ISO 20022 overview", publisher="ISO", url="https://www.iso20022.org/", date_reviewed="2026-07-11", license_status_note="Standards metadata reference; no standard text copied.", derived_rule="Financial message, settlement, fee, and currency consistency patterns."),
    ],
    "insurance": [
        ScenarioReference(reference_name="SynthETIC insurance claim simulator", publisher="Actuarial research community", url="https://github.com/agi-lab/SynthETIC", date_reviewed="2026-07-11", license_status_note="Open-source synthetic simulator reference; no rows copied.", derived_rule="Claim development, settlement delay, and claim dependency patterns."),
        ScenarioReference(reference_name="NAIC consumer insurance topics", publisher="National Association of Insurance Commissioners", url="https://content.naic.org/consumer.htm", date_reviewed="2026-07-11", license_status_note="Public information reference.", derived_rule="Policy, premium, claim, renewal, and coverage concepts."),
    ],
    "education": [
        ScenarioReference(reference_name="IPEDS", publisher="National Center for Education Statistics", url="https://nces.ed.gov/ipeds/", date_reviewed="2026-07-11", license_status_note="Government statistics reference; no rows copied.", derived_rule="Institution, enrollment, completion, fee, and outcome relationships."),
        ScenarioReference(reference_name="Common Education Data Standards", publisher="U.S. Department of Education", url="https://ceds.ed.gov/", date_reviewed="2026-07-11", license_status_note="Public data-standard reference.", derived_rule="Education entity and outcome consistency patterns."),
    ],
    "ecommerce": [
        ScenarioReference(reference_name="UCI Online Retail", publisher="UCI Machine Learning Repository", url="https://archive.ics.uci.edu/", date_reviewed="2026-07-11", license_status_note="Metadata reference only; no rows copied.", derived_rule="Order, cart, payment, shipment, return, and review lifecycle patterns."),
        ScenarioReference(reference_name="Stripe idempotency documentation", publisher="Stripe", url="https://docs.stripe.com/api/idempotent_requests", date_reviewed="2026-07-11", license_status_note="API documentation reference.", derived_rule="Payment retry and idempotency failure scenarios."),
    ],
}


def scenario(
    *,
    domain: str,
    scenario_id: str,
    name: str,
    category: str,
    subcategory: str,
    issue_type: str,
    table: str,
    column: str | None,
    affected_tables: list[str],
    validations: list[str],
    business_problem: str,
    technical_problem: str,
    tags: list[str],
    aliases: list[str],
    modes: list[str] | None = None,
    event_types: list[str] | None = None,
    profiles: list[str] | None = None,
) -> ScenarioDefinition:
    supported_modes = modes or ["batch"]
    default_mode = "streaming" if supported_modes == ["streaming"] else "batch"
    profiles = profiles or ["realistic", "stress"]
    failure = FailureSpecification(
        failure_id=f"{scenario_id}_failure",
        issue_type=issue_type,
        table=table,
        column=column,
        event_type=(event_types or [None])[0],
        mutation_strategy=f"Apply controlled {issue_type} mutation to {table}",
        expected_validation_id=validations[0],
    )
    variation_slug = scenario_id.split("_", 1)[-1]
    variations = [
        ScenarioVariation(variation_id="default", name="Default", description="Default deterministic controlled mutation.", supported_modes=supported_modes),
        ScenarioVariation(variation_id=f"{variation_slug}_low", name="Low impact", description="Lower-rate variation for smoke tests.", configuration_overrides={"severity": "low"}, supported_modes=supported_modes, recommended_severity="low"),
        ScenarioVariation(variation_id=f"{variation_slug}_stress", name="Stress", description="Higher-rate variation for stress testing.", configuration_overrides={"severity": "stress"}, supported_modes=supported_modes, recommended_severity="stress"),
    ]
    title = name
    return ScenarioDefinition(
        scenario_id=scenario_id,
        name=title,
        slug=scenario_id.replace("_", "-"),
        domain=domain,
        category=category,
        subcategory=subcategory,
        short_description=business_problem,
        detailed_description=f"{business_problem} {technical_problem}",
        business_problem=business_problem,
        technical_problem=technical_problem,
        intended_users=["data_engineer", "qa_engineer", "analytics_engineer", "ml_engineer"],
        supported_modes=supported_modes,
        default_mode=default_mode,
        supported_output_formats=["csv", "json", "parquet", "database"],
        recommended_realism_profiles=profiles,
        default_realism_profile=profiles[0],
        primary_transaction_table=PRIMARY_TABLES[domain],
        affected_tables=affected_tables,
        affected_columns=[column] if column else [],
        affected_event_types=event_types or [],
        required_tables=sorted(set([table, *affected_tables])),
        prerequisite_entities=["valid clean baseline", "domain relationships generated by DataForge"],
        failure_injections=[failure],
        expected_validations=validations,
        expected_pipeline_behavior="Pipeline should quarantine affected records/events, surface failed validations, and preserve clean unaffected records.",
        success_criteria=["Clean baseline validates at 100 before mutation.", "Configured issue count is controlled and reproducible.", "Expected validation failures are detected."],
        failure_criteria=["Unexpected clean baseline failure.", "Mutation exceeds configured safe rate.", "Expected validation is not detected."],
        supported_variations=variations,
        configurable_parameters={"rate": {"low": 0.01, "medium": 0.03, "high": 0.05, "stress": 0.10}},
        tags=sorted(set(tags + [domain, category, issue_type])),
        aliases=aliases,
        natural_language_examples=[
            f"Generate {domain} data for {title.lower()} with medium severity.",
            f"Run {scenario_id} in CSV with 10000 records.",
        ],
        references=REFERENCE_SETS[domain],
        assumptions=["Scenario failures are synthetic and deterministic.", "Reference sources are used only for metadata, rules, and patterns."],
        limitations=["Scenario uses shared DataForge issue primitives; highly specialized custom row mutation may be added later if beta users need it."],
    )

