export type Domain = "retail" | "healthcare" | "finance" | "insurance" | "logistics" | "banking" | "manufacturing" | "telecommunications" | "education" | "ecommerce";
export type LoadType = "bulk" | "incremental" | "delta" | "cdc" | "event_stream";
export type OutputFormat = "csv" | "json" | "parquet" | "database";
export type DatabaseType = "postgresql" | "mssql" | "mysql";
export type StreamingDomain = "manufacturing" | "telecommunications" | "ecommerce" | "logistics" | "banking";

export type StreamPayload = {
  domain: StreamingDomain;
  event_types: string[];
  events_per_second: number;
  duration_minutes: number;
  format: "json";
  seed: number;
  failure_injections: Record<string, boolean | number>;
  webhook_url?: string;
  webhook_secret?: string;
};

export type StreamStartResponse = {
  stream_id: string;
  status: string;
  domain: StreamingDomain;
  started_at: string;
  estimated_end_at: string;
  events_per_second: number;
  duration_minutes: number;
  pull_url: string | null;
  sse_url: string | null;
  latest_url: string | null;
  event_type_urls: Record<string, string>;
  stream_token: string | null;
  stream_token_expires_at: string | null;
};

export type StreamStatus = {
  stream_id: string;
  domain: StreamingDomain;
  status: "queued" | "running" | "completed" | "stopped" | "failed" | string;
  events_generated: number;
  events_failed: number;
  started_at: string;
  estimated_end_at: string;
  completed_at: string | null;
  failure_summary: Record<string, number>;
  webhook_delivery_summary: Record<string, number | string | null>;
};

export type StreamEvent = {
  event_id: string;
  event_type: string;
  domain: StreamingDomain;
  event_time: string;
  ingestion_time: string;
  sequence_number: number;
  correlation_id: string;
  payload: Record<string, unknown>;
  injected_issues: string[];
};

export type StreamEventsResponse = {
  stream_id: string;
  total: number;
  events: StreamEvent[];
};

export type StreamLatestEventResponse = {
  stream_id: string;
  event: StreamEvent;
};

export type StreamValidationReport = {
  run_id: string;
  domain: StreamingDomain;
  load_type: "event_stream";
  format: "json";
  record_count: number;
  quality_score: number;
  status: "PASS" | "FAIL" | string;
  summary: { total_checks: number; passed: number; failed: number };
  issues: { type: string; count: number }[];
  checks: { name: string; status: "PASS" | "FAIL" | string; expected: string; actual: string }[];
  generated_at: string;
};

export type CatalogTable = {
  name: string;
  primary_key: string;
  columns: string[];
  foreign_keys: { column: string; references_table: string; references_column: string }[];
};

export type CatalogResponse = {
  domain: Domain;
  tables: CatalogTable[];
};

export type GeneratePayload = {
  domain: Domain;
  load_type: LoadType;
  format: OutputFormat;
  database_type?: DatabaseType;
  records: number;
  selected_tables: string[];
  issues: Record<string, number>;
  user_email?: string;
};

export type GenerateResponse = {
  job_id: string;
  status: string;
  run_id: string | null;
};

export type RunSummary = {
  id: string;
  domain: Domain;
  load_type: LoadType;
  format: OutputFormat;
  record_count: number;
  status: string;
  quality_score: number | null;
  started_at: string;
  completed_at: string | null;
  scenario_id: string | null;
  scenario_name: string | null;
  scenario_outcome: string | null;
  scenario_severity: string | null;
  scenario_variations: string[];
};

export type PaginatedRuns = {
  total: number;
  limit: number;
  offset: number;
  items: RunSummary[];
};

export type RunDetail = RunSummary & {
  generated_files: {
    id: string;
    file_name: string;
    file_path: string;
    storage_backend: string;
    object_key: string;
    file_format: OutputFormat;
    size_bytes: number;
    file_size_mb: number;
    content_type: string;
    created_at: string;
  }[];
  issue_manifest: {
    id: number;
    issue_type: string;
    issue_count: number;
    issue_percentage: number;
    created_at: string;
  }[];
  validation_results: {
    id: number;
    validation_name: string;
    status: "PASS" | "FAIL" | string;
    quality_score: number | null;
    expected_value: string;
    actual_value: string;
    created_at: string;
  }[];
  scenario_reports: {
    "scenario_execution_report.json"?: {
      ground_truth?: GroundTruthRow[];
      scenario_validator_results?: {
        validation_id: string;
        status: string;
        expected_count: number;
        detected_count: number;
        affected_entities: unknown[];
        affected_tables?: string[];
        severity: string;
        message: string;
        evidence: Record<string, unknown>;
        reconciliation_status: string;
      }[];
    };
  };
};

export type JobStatus = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed" | string;
  run_id: string | null;
  error_message: string | null;
  queued_at: string;
  started_at: string | null;
  completed_at: string | null;
  run: RunDetail | null;
};

export type FilePreview = {
  file_id: string;
  file_name: string;
  file_format: OutputFormat;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  max_rows: number;
};

export type AnalyticsOverview = {
  datasets_generated: number;
  validation_runs: number;
  average_quality_score: number;
  most_used_domain: string | null;
  most_used_format: string | null;
  most_used_load_type: string | null;
};

export type ScenarioSummary = {
  scenario_id: string;
  version: string;
  name: string;
  domain: Domain;
  category: string;
  subcategory: string;
  short_description: string;
  supported_modes: string[];
  default_mode: "batch" | "streaming";
  default_realism_profile: string;
  default_record_count: number;
  default_severity: string;
  tags: string[];
};

export type ScenarioDetail = ScenarioSummary & {
  slug: string;
  detailed_description: string;
  business_problem: string;
  technical_problem: string;
  supported_output_formats: OutputFormat[];
  recommended_realism_profiles: string[];
  primary_transaction_table: string;
  affected_tables: string[];
  affected_columns: string[];
  affected_event_types: string[];
  required_tables: string[];
  failure_injections: Record<string, unknown>[];
  expected_validations: string[];
  expected_quality_status: string;
  expected_pipeline_behavior: string;
  success_criteria: string[];
  failure_criteria: string[];
  severity_levels: string[];
  supported_variations: { variation_id: string; name: string; description: string; recommended_severity: string }[];
  natural_language_examples: string[];
  references: { reference_name: string; publisher: string; url: string; no_copied_rows: boolean }[];
  assumptions: string[];
  limitations: string[];
};

export type ScenarioListResponse = {
  total: number;
  items: ScenarioSummary[];
};

export type ScenarioLibrarySummary = {
  scenario_id: string;
  scenario_name: string;
  description: string;
  domain: Domain;
  business_process: string;
  severity: string;
  failure_category: string;
  failure_primitive: string;
  failure_display_name: string;
  validator_pattern: string;
  v1_ready: boolean;
  execution_status: "executable" | "custom_reference" | "specification_only" | string;
  implementation_readiness: string;
};

export type ScenarioLibraryListResponse = {
  total: number;
  returned: number;
  quality_summary: {
    total_runtime_capable: number;
    v1_ready: number;
    needs_fix: number;
  };
  items: ScenarioLibrarySummary[];
};

export type FailurePlanFailure = {
  primitive_id: string;
  mode: "percentage" | "exact_count";
  value: number;
  table?: string;
  column?: string | null;
  seed_offset?: number;
};

export type FailurePlan = {
  scenario_id: string;
  seed: number;
  overlap_mode: "non_overlapping" | "allow_overlap";
  failures: FailurePlanFailure[];
};

export type ScenarioBuilderGeneratePayload = {
  scenario_id: string;
  records: number;
  output_format: "csv" | "json" | "parquet";
  seed: number;
  severity: string;
  failure_plan: FailurePlan;
  requested_by?: string;
};

export type ScenarioBuilderConfiguration = {
  scenario: {
    scenario_id: string;
    scenario_name: string;
    domain: Domain;
    business_process: string;
    description: string;
    business_rule: string;
    example_failure: string;
    severity: string;
    entity: string;
    failure_category: string;
    execution_status: string;
    v1_ready: boolean;
    quality_status: string;
    validator_detection_strategy: string;
    technical_details: {
      primitive_id: string;
      validator_id: string;
      semantic_mappings: string[];
    };
  };
  required_tables: {
    table: string;
    role: string;
    estimated_rows: number;
    business_purpose: string;
  }[];
  default_failure_plan: {
    scenario_id: string;
    seed: number;
    overlap_mode: "non_overlapping" | "allow_overlap";
    failures: FailurePlanPreviewFailure[];
  };
  compatible_primitives: {
    primitive_id: string;
    display_name: string;
    default_mode: "percentage";
    default_value: number;
    target_table: string;
    target_column: string | null;
    supported: boolean;
    unavailable_reason: string | null;
    validator: string;
  }[];
  parameter_schema: Record<string, unknown>;
  manufacturing_field_audit: Record<string, { classification: string; reason: string }>;
};

export type FailurePlanPreviewFailure = {
  primitive_id: string;
  display_name: string;
  mode: "percentage" | "exact_count";
  value: number;
  target_table: string;
  target_column: string | null;
  target_entity: string;
  estimated_affected: number;
  estimated_from_rows: number;
  validator: string;
  technical: { primitive_id: string; validator_id: string };
};

export type FailurePlanPreview = {
  scenario_id: string;
  valid: boolean;
  errors: string[];
  records: number;
  overlap_mode: "non_overlapping" | "allow_overlap";
  failures: FailurePlanPreviewFailure[];
  estimated_total_affected_entities: number;
  warnings: string[];
};

export type GroundTruthRow = {
  primitive_id: string;
  display_name: string;
  requested: { mode: string; value: number };
  target: { table: string; column?: string | null; entity: string };
  expected_count: number;
  selected_count: number;
  actual_count: number;
  detected_count: number;
  detection_rate: number;
  affected_entities: unknown[];
  evidence: Record<string, unknown>;
  reconciliation_status: string;
};

export type ScenarioTemplate = {
  id: string;
  name: string;
  description: string | null;
  domain: Domain;
  scenario_id: string;
  records: number;
  output_format: "csv" | "json" | "parquet";
  severity: string;
  seed_behavior: "fixed_seed" | "new_seed_each_run";
  failure_plan: FailurePlan;
  failure_count: number;
  compatibility: { valid: boolean; errors: string[]; warnings: string[] };
  created_at: string;
  updated_at: string;
  last_used_at: string | null;
};

export type ScenarioBuilderRunSummary = RunSummary & {
  seed: number | null;
  tables_generated: number;
  failure_plan: FailurePlan | null;
  overlap_mode: string | null;
  ground_truth_summary: {
    failure_count: number;
    selected_count: number;
    actual_count: number;
    detected_count: number;
    injection_success_rate: number;
    detection_rate: number;
  };
  duration_seconds: number | null;
};

export type EvaluationMetrics = {
  true_positive: number;
  false_positive: number;
  true_negative: number;
  false_negative: number;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  false_positive_rate: number | null;
  detection_coverage: number | null;
};

export type EvaluationResult = {
  id: string;
  scenario_run_id: string;
  benchmark_id: string | null;
  benchmark_version: string | null;
  detector_name: string;
  detector_version: string | null;
  detector_output_format: "json" | "jsonl" | "csv" | "api";
  detector_output_checksum: string | null;
  detector_output_artifact: string | null;
  result_artifact: string | null;
  status: string;
  metrics: EvaluationMetrics;
  per_failure_metrics: (EvaluationMetrics & { primitive_id: string })[];
  acceptance: { status: string; failures: Record<string, unknown>[] };
  false_positive_examples: Record<string, unknown>[];
  false_negative_examples: Record<string, unknown>[];
  unknown_detections: Record<string, unknown>[];
  started_at: string;
  completed_at: string | null;
  created_at: string;
};

export type BenchmarkDefinition = {
  id: string;
  name: string;
  slug: string;
  version: string;
  description: string | null;
  domain: Domain;
  scenario_id: string;
  scenario_template_id: string | null;
  records: number;
  output_format: "csv" | "json" | "parquet";
  seed: number;
  failure_plan: FailurePlan;
  evaluation_unit: string;
  thresholds: Record<string, number>;
  snapshot: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type BenchmarkRun = {
  id: string;
  benchmark_id: string;
  benchmark_version: string;
  domain: Domain;
  scenario_id: string;
  scenario_run_id: string | null;
  generation_job_id: string | null;
  evaluation_run_id: string | null;
  status: string;
  status_reason: string | null;
  detector_mode: "manual_upload" | "api_submission" | string;
  detector_status: string;
  detector_name: string | null;
  detector_version: string | null;
  dataset_status: string;
  ground_truth_status: string;
  evaluation_status: string;
  result: "PASS" | "FAIL" | string | null;
  acceptance: { status: string; failures: Record<string, unknown>[] } | null;
  metrics: EvaluationMetrics | null;
  artifact_manifest: Record<string, unknown> | null;
  snapshot: Record<string, unknown> | null;
  retain_until: string | null;
  created_at: string;
  started_at: string | null;
  updated_at: string;
  completed_at: string | null;
  errors: string[];
  warnings: string[];
};

export type ScenarioRunComparison = {
  left_run_id: string;
  right_run_id: string;
  comparison: Record<string, unknown>;
};

export type ScenarioConfigPayload = {
  scenario_id: string;
  mode?: "batch" | "streaming";
  realism_profile?: string;
  records?: number;
  output_format?: OutputFormat;
  database_type?: DatabaseType;
  seed?: number;
  severity?: string;
  variation_ids?: string[];
  table_selection?: string[];
  requested_by?: string;
};

export type ScenarioValidationResponse = {
  status: "PASS" | "FAIL";
  resolved_config: ScenarioConfigPayload | null;
  errors: string[];
  warnings: string[];
};
