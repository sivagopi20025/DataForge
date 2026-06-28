export type Domain = "retail" | "healthcare" | "finance" | "insurance" | "logistics" | "banking";
export type LoadType = "bulk" | "incremental" | "delta" | "cdc" | "event_stream";
export type OutputFormat = "csv" | "json" | "parquet";

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
  started_at: string;
  completed_at: string | null;
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
