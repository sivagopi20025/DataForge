from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .domains import DOMAIN_GENERATORS, DOMAIN_SPECS
from .exporter import export_run
from .injector import FailureInjector
from .modes import build_artifacts, normalize_load_type
from .validation import reconciliation_report, relationship_report, schema_report, validate


def boolean(value: str) -> bool:
    lowered = value.lower()
    if lowered in {"true", "1", "yes", "y"}:
        return True
    if lowered in {"false", "0", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Generate DataForge domain test data")
    result.add_argument("--domain", choices=tuple(sorted(DOMAIN_SPECS)), default="retail")
    result.add_argument("--records", type=int, default=10_000, help="number of primary fact records: sales for retail, shipments for logistics")
    result.add_argument("--load-type", choices=("bulk", "incremental", "delta", "cdc", "event", "event_stream"), default="bulk")
    result.add_argument("--inject-failures", type=boolean, default=False)
    result.add_argument("--failure-profile", choices=("low", "medium", "high"), default="medium")
    result.add_argument("--output-format", nargs="+", choices=("csv", "json", "parquet"), default=["csv"], help="one or more formats, for example: csv json")
    result.add_argument("--tables", nargs="+", default=["all"], help="all, one table, or a space/comma-separated table list")
    result.add_argument("--scd-type", choices=(1, 2), type=int, default=1)
    result.add_argument("--last-successful-load-timestamp", help="ISO-8601 watermark for incremental generation")
    result.add_argument("--seed", type=int, default=42)
    result.add_argument("--output", type=Path, default=Path("output"), help="base output directory")
    result.add_argument("--dataset-name", default="sample", help="name used for the dataset and run folders")
    return result


def create_run_directory(base: Path, dataset_name: str, generated_at: datetime) -> Path:
    safe_name = "".join(character for character in dataset_name.strip() if character.isalnum() or character in {"-", "_"})
    if not safe_name:
        raise ValueError("dataset name must contain a letter, number, hyphen, or underscore")
    timestamp = generated_at.strftime("%Y%m%dT%H%M%S%fZ")
    return base / safe_name / f"{safe_name}_{timestamp}"


def _selected_tables(raw_tables: list[str], valid_tables: set[str]) -> set[str]:
    requested_tables = [item.strip() for value in raw_tables for item in value.split(",") if item.strip()]
    if "all" in requested_tables:
        if len(requested_tables) != 1:
            raise SystemExit("--tables all cannot be combined with individual table names")
        return set(valid_tables)
    unknown_tables = sorted(set(requested_tables) - valid_tables)
    if unknown_tables:
        raise SystemExit(f"Unknown table(s): {', '.join(unknown_tables)}. Valid tables: {', '.join(sorted(valid_tables))}")
    if not requested_tables:
        raise SystemExit("--tables requires all or at least one table name")
    return set(requested_tables)


def _profile(domain: str, profile: str) -> dict[str, float]:
    domain_path = Path(__file__).resolve().parent.parent / "config" / f"{domain}.json"
    fallback_path = Path(__file__).resolve().parent.parent / "config" / "retail.json"
    path = domain_path if domain_path.exists() else fallback_path
    return json.loads(path.read_text(encoding="utf-8"))["profiles"][profile]


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    spec = DOMAIN_SPECS[args.domain]
    generator_type = DOMAIN_GENERATORS[args.domain]
    selected_tables = _selected_tables(args.tables, set(spec.schemas))
    normalized_load_type = normalize_load_type(args.load_type)

    if normalized_load_type == "cdc" and not (selected_tables & set(spec.cdc_tables)):
        raise SystemExit(f"CDC mode for {args.domain} supports: {', '.join(spec.cdc_tables)}")
    event_tables = {definition.table for definition in spec.event_definitions}
    if normalized_load_type == "event_stream" and not (selected_tables & event_tables):
        raise SystemExit(f"Event stream mode for {args.domain} supports: {', '.join(sorted(event_tables))}")

    generated_at = datetime.now(timezone.utc)
    run_output = create_run_directory(args.output, args.dataset_name, generated_at)
    if normalized_load_type == "incremental" and not args.last_successful_load_timestamp:
        args.last_successful_load_timestamp = "2026-06-21T00:00:00+00:00"

    generator = generator_type(args.records, args.seed, normalized_load_type, args.scd_type)
    if hasattr(generator, "selected_tables") and selected_tables != set(spec.schemas):
        generator.selected_tables = selected_tables
    clean = generator.generate()
    data = clean
    failures = []
    if args.inject_failures:
        data, failures = FailureInjector(_profile(args.domain, args.failure_profile), args.seed, spec).apply(clean, selected_tables)

    full_selection = selected_tables == set(spec.schemas)
    report_selection = None if full_selection else selected_tables
    quality = validate(data, spec, report_selection)
    relationships = relationship_report(data, spec, report_selection)
    schemas = schema_report(data, spec, report_selection)
    reconciliation = reconciliation_report(data, spec, report_selection)
    artifacts = build_artifacts(data, normalized_load_type, args.seed, selected_tables, spec)
    metadata = {
        "generator": "dataforge",
        "version": "0.6.0",
        "domain": args.domain,
        "dataset_name": args.dataset_name,
        "run_id": run_output.name,
        "generated_at": generated_at.isoformat(),
        "seed": args.seed,
        "requested_records": args.records,
        "selected_tables": sorted(selected_tables),
        "load_type": normalized_load_type,
        "output_formats": args.output_format,
        "scd_type": args.scd_type,
        "last_successful_load_timestamp": args.last_successful_load_timestamp,
        "failure_profile": args.failure_profile if args.inject_failures else None,
    }
    reports = {
        "quality_report.json": quality,
        "relationship_report.json": relationships,
        "schema_report.json": schemas,
        "reconciliation_report.json": reconciliation,
    }
    export_run(run_output, artifacts, args.output_format, metadata, reports, failures)
    file_count = len(artifacts) * len(args.output_format)
    print(f"Generated {len(artifacts)} {normalized_load_type} {args.domain} datasets in {len(args.output_format)} format(s) ({file_count} files) in {run_output.resolve()}")
    print(f"Quality status: {quality['overall_status']}; injected failures: {sum(e.count for e in failures)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
