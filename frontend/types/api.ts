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
  run_id: string;
  status: string;
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

export type RunDetail = RunSummary & {
  generated_files: {
    id: string;
    file_name: string;
    file_path: string;
    file_format: OutputFormat;
    file_size_mb: number;
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

export type AnalyticsOverview = {
  datasets_generated: number;
  validation_runs: number;
  average_quality_score: number;
  most_used_domain: string | null;
  most_used_format: string | null;
  most_used_load_type: string | null;
};
