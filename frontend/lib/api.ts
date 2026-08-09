import axios from "axios";
import type {
  AnalyticsOverview,
  CatalogResponse,
  Domain,
  FilePreview,
  GeneratePayload,
  GenerateResponse,
  JobStatus,
  PaginatedRuns,
  RunDetail,
  ScenarioConfigPayload,
  ScenarioBuilderConfiguration,
  ScenarioBuilderGeneratePayload,
  ScenarioLibraryListResponse,
  ScenarioDetail,
  FailurePlan,
  FailurePlanPreview,
  ScenarioListResponse,
  ScenarioValidationResponse,
  StreamEventsResponse,
  StreamLatestEventResponse,
  StreamPayload,
  StreamStartResponse,
  StreamStatus,
  StreamValidationReport,
  ScenarioTemplate,
  ScenarioBuilderRunSummary,
  BenchmarkDefinition,
  BenchmarkRun,
  EvaluationResult,
  ScenarioRunComparison,
} from "@/types/api";

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010",
  timeout: 120000,
});

const browserApiKey = process.env.NEXT_PUBLIC_ENABLE_DEMO_API_KEY === "true" ? process.env.NEXT_PUBLIC_DATAFORGE_API_KEY : undefined;
if (browserApiKey) {
  api.defaults.headers.common["X-API-Key"] = browserApiKey;
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.error ?? error.message ?? "Unable to reach DataForge backend.";
    return Promise.reject(new Error(message));
  },
);

export async function getCatalogTables(domain: Domain) {
  const { data } = await api.get<CatalogResponse>(`/api/v1/catalog/tables/${domain}`);
  return data;
}

export async function generateDataset(payload: GeneratePayload) {
  const { data } = await api.post<GenerateResponse>("/api/v1/generate", payload);
  return data;
}

export async function getRun(runId: string) {
  const { data } = await api.get<RunDetail>(`/api/v1/runs/${runId}`);
  return data;
}

export async function getRuns(limit = 25, offset = 0) {
  const { data } = await api.get<PaginatedRuns>("/api/v1/runs", { params: { limit, offset } });
  return data;
}

export async function deleteRun(runId: string) {
  const { data } = await api.delete<{ deleted: number; requested: number; run_ids: string[] }>(`/api/v1/runs/${runId}`);
  return data;
}

export async function deleteRuns(runIds: string[]) {
  const { data } = await api.post<{ deleted: number; requested: number; run_ids: string[] }>("/api/v1/runs/delete", { run_ids: runIds });
  return data;
}

export async function getJob(jobId: string) {
  const { data } = await api.get<JobStatus>(`/api/v1/jobs/${jobId}`);
  return data;
}

export async function waitForJob(jobId: string, timeoutMs = 120000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const job = await getJob(jobId);
    if (job.status === "completed") {
      return job;
    }
    if (job.status === "failed") {
      throw new Error(job.error_message ?? "Generation job failed.");
    }
    await new Promise((resolve) => window.setTimeout(resolve, 1200));
  }
  throw new Error("Generation job timed out. Check run history for status.");
}

export function getDownloadUrl(runId: string, fileId: string) {
  const baseUrl = api.defaults.baseURL ?? "";
  return `${baseUrl}/api/v1/runs/${runId}/files/${fileId}/download`;
}

export function getRunDownloadUrl(runId: string) {
  const baseUrl = api.defaults.baseURL ?? "";
  return `${baseUrl}/api/v1/runs/${runId}/download`;
}

export async function getFilePreview(runId: string, fileId: string, rows = 50) {
  const { data } = await api.get<FilePreview>(`/api/v1/runs/${runId}/files/${fileId}/preview`, { params: { rows } });
  return data;
}

export async function startStream(payload: StreamPayload) {
  const { data } = await api.post<StreamStartResponse>("/api/v1/streams/start", payload);
  return data;
}

export async function getStream(streamId: string) {
  const { data } = await api.get<StreamStatus>(`/api/v1/streams/${streamId}`);
  return data;
}

export async function getStreamEvents(streamId: string, limit = 100, offset = 0, streamToken?: string | null, afterSequence?: number | null) {
  const { data } = await api.get<StreamEventsResponse>(`/api/v1/streams/${streamId}/events`, {
    params: { limit, offset, after_sequence: afterSequence ?? undefined },
    headers: streamAuthHeaders(streamToken),
  });
  return data;
}

export async function getStreamEventsByType(streamId: string, eventType: string, limit = 100, offset = 0, streamToken?: string | null, afterSequence?: number | null) {
  const { data } = await api.get<StreamEventsResponse>(`/api/v1/streams/${streamId}/events/${eventType}`, {
    params: { limit, offset, after_sequence: afterSequence ?? undefined },
    headers: streamAuthHeaders(streamToken),
  });
  return data;
}

export async function getLatestStreamEvent(streamId: string, streamToken?: string | null) {
  const { data } = await api.get<StreamLatestEventResponse>(`/api/v1/streams/${streamId}/events/latest`, {
    headers: streamAuthHeaders(streamToken),
  });
  return data;
}

export async function stopStream(streamId: string) {
  const { data } = await api.post<StreamStatus>(`/api/v1/streams/${streamId}/stop`);
  return data;
}

export async function replayStream(streamId: string) {
  const { data } = await api.post<StreamEventsResponse>(`/api/v1/streams/${streamId}/replay`);
  return data;
}

export async function getStreamValidation(streamId: string) {
  const { data } = await api.get<StreamValidationReport>(`/api/v1/streams/${streamId}/validation`);
  return data;
}

export function getStreamSseUrl(streamId: string, streamToken?: string | null, eventType?: string | null) {
  const baseUrl = api.defaults.baseURL ?? "";
  const suffix = eventType ? `/${eventType}` : "";
  return `${baseUrl}/api/v1/streams/${streamId}/sse${suffix}`;
}

function streamAuthHeaders(streamToken?: string | null) {
  return streamToken ? { Authorization: `Bearer ${streamToken}` } : undefined;
}

export async function getAnalyticsOverview() {
  const { data } = await api.get<AnalyticsOverview>("/api/v1/admin/analytics/overview");
  return data;
}

export async function getAnalyticsMap(path: string) {
  const { data } = await api.get<Record<string, number>>(`/api/v1/admin/analytics/${path}`);
  return data;
}

export async function getQualityTrends() {
  const { data } = await api.get<{ date: string; average_quality_score: number }[]>("/api/v1/admin/analytics/quality/trends");
  return data;
}

export async function getQualityRuns(kind: "lowest" | "highest") {
  const endpoint = kind === "lowest" ? "lowest-runs" : "highest-runs";
  const { data } = await api.get<{ run_id: string; domain: string; load_type: string; quality_score: number }[]>(
    `/api/v1/admin/analytics/quality/${endpoint}`,
  );
  return data;
}

export async function getScenarios(params?: { domain?: string; category?: string; mode?: string; keyword?: string }) {
  const { data } = await api.get<ScenarioListResponse>("/api/v1/scenarios", { params });
  return data;
}

export async function getScenario(scenarioId: string) {
  const { data } = await api.get<ScenarioDetail>(`/api/v1/scenarios/${scenarioId}`);
  return data;
}

export async function validateScenarioConfig(scenarioId: string, payload: ScenarioConfigPayload) {
  const { data } = await api.post<ScenarioValidationResponse>(`/api/v1/scenarios/${scenarioId}/validate-config`, payload);
  return data;
}

export async function runScenario(scenarioId: string, payload: ScenarioConfigPayload) {
  const { data } = await api.post<GenerateResponse>(`/api/v1/scenarios/${scenarioId}/run`, payload);
  return data;
}

export async function getScenarioLibraryItems(params?: {
  domain?: string;
  business_process?: string;
  failure_category?: string;
  severity?: string;
  execution_status?: string;
  v1_ready?: boolean;
  limit?: number;
}) {
  const { data } = await api.get<ScenarioLibraryListResponse>("/api/v1/scenario-library/scenarios", { params });
  return data;
}

export async function getScenarioBuilderConfiguration(scenarioId: string, records = 10000) {
  const { data } = await api.get<ScenarioBuilderConfiguration>(`/api/v1/scenario-library/scenarios/${scenarioId}/configuration`, { params: { records } });
  return data;
}

export async function previewFailurePlan(scenarioId: string, records: number, failurePlan: FailurePlan) {
  const { data } = await api.post<FailurePlanPreview>("/api/v1/scenario-library/failure-plan/preview", {
    scenario_id: scenarioId,
    records,
    failure_plan: failurePlan,
  });
  return data;
}

export async function generateScenarioBuilderDataset(payload: ScenarioBuilderGeneratePayload) {
  const { data } = await api.post<GenerateResponse>("/api/v1/scenario-library/generate", payload);
  return data;
}

export async function getScenarioTemplates() {
  const { data } = await api.get<{ total: number; items: ScenarioTemplate[] }>("/api/v1/scenario-library/templates");
  return data;
}

export async function createScenarioTemplate(payload: {
  name: string;
  description?: string;
  scenario_id: string;
  records: number;
  output_format: "csv" | "json" | "parquet";
  severity: string;
  seed_behavior: "fixed_seed" | "new_seed_each_run";
  failure_plan: FailurePlan;
}) {
  const { data } = await api.post<ScenarioTemplate>("/api/v1/scenario-library/templates", payload);
  return data;
}

export async function deleteScenarioTemplate(templateId: string) {
  const { data } = await api.delete<{ deleted: boolean; template_id: string }>(`/api/v1/scenario-library/templates/${templateId}`);
  return data;
}

export async function prepareScenarioTemplateRun(templateId: string) {
  const { data } = await api.post<{ status: string; template: ScenarioTemplate; generation_request: ScenarioBuilderGeneratePayload }>(`/api/v1/scenario-library/templates/${templateId}/prepare-run`);
  return data;
}

export async function getScenarioBuilderRuns() {
  const { data } = await api.get<{ total: number; items: ScenarioBuilderRunSummary[] }>("/api/v1/scenario-library/runs");
  return data;
}

export async function prepareScenarioRerun(runId: string) {
  const { data } = await api.post<{ status: string; run_id: string; generation_request: ScenarioBuilderGeneratePayload }>(`/api/v1/scenario-library/runs/${runId}/prepare-rerun`);
  return data;
}

export function getScenarioGroundTruthUrl(runId: string, format: "json" | "jsonl" | "csv" = "jsonl") {
  const baseUrl = api.defaults.baseURL ?? "";
  return `${baseUrl}/api/v1/scenario-library/runs/${runId}/ground-truth?format=${format}`;
}

export async function getScenarioManifest(runId: string) {
  const { data } = await api.get<Record<string, unknown>>(`/api/v1/scenario-library/runs/${runId}/manifest`);
  return data;
}

export async function compareScenarioBuilderRuns(leftRunId: string, rightRunId: string) {
  const { data } = await api.post<ScenarioRunComparison>("/api/v1/scenario-library/runs/compare", { left_run_id: leftRunId, right_run_id: rightRunId });
  return data;
}

export async function createEvaluation(payload: {
  run_id: string;
  detector_name: string;
  detector_version?: string | null;
  detector_output_format?: "json" | "jsonl" | "csv" | "api";
  detections: Record<string, unknown>[];
  label_mapping?: Record<string, string>;
  benchmark_id?: string | null;
}) {
  const { data } = await api.post<EvaluationResult>("/api/v1/evaluations", payload);
  return data;
}

export async function getEvaluations() {
  const { data } = await api.get<{ total: number; items: EvaluationResult[] }>("/api/v1/evaluations");
  return data;
}

export async function createBenchmark(payload: {
  name: string;
  description?: string;
  domain: Domain;
  scenario_id: string;
  records: number;
  output_format: "csv" | "json" | "parquet";
  seed: number;
  failure_plan: FailurePlan;
  thresholds: Record<string, number>;
}) {
  const { data } = await api.post<BenchmarkDefinition>("/api/v1/benchmarks", payload);
  return data;
}

export async function getBenchmarks() {
  const { data } = await api.get<{ total: number; items: BenchmarkDefinition[] }>("/api/v1/benchmarks");
  return data;
}

export async function runBenchmark(
  benchmarkId: string,
  payload: {
    run_id: string;
    detector_name: string;
    detector_version?: string | null;
    detector_output_format?: "json" | "jsonl" | "csv" | "api";
    detections: Record<string, unknown>[];
    label_mapping?: Record<string, string>;
  },
) {
  const { data } = await api.post<EvaluationResult>(`/api/v1/benchmarks/${benchmarkId}/runs`, payload);
  return data;
}

export async function launchBenchmarkRun(
  benchmarkId: string,
  payload: { seed?: number; seed_mode?: "fixed" | "random"; detector_mode?: "manual_upload" | "api_submission" },
  idempotencyKey?: string,
) {
  const { data } = await api.post<{ benchmark_run_id: string; status: string }>(`/api/v1/benchmarks/${benchmarkId}/runs`, payload, {
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
  });
  return data;
}

export async function getBenchmarkRuns(params?: { benchmark_id?: string; status?: string; domain?: Domain; scenario_id?: string; result?: string; limit?: number; offset?: number }) {
  const { data } = await api.get<{ total: number; limit: number; offset: number; items: BenchmarkRun[] }>("/api/v1/benchmark-runs", { params });
  return data;
}

export async function getBenchmarkRun(benchmarkRunId: string) {
  const { data } = await api.get<BenchmarkRun>(`/api/v1/benchmark-runs/${benchmarkRunId}`);
  return data;
}

export async function cancelBenchmarkRun(benchmarkRunId: string) {
  const { data } = await api.post<BenchmarkRun>(`/api/v1/benchmark-runs/${benchmarkRunId}/cancel`);
  return data;
}

export async function submitBenchmarkDetectorOutput(
  benchmarkRunId: string,
  payload: {
    detector_name: string;
    detector_version?: string | null;
    detector_output_format?: "json" | "jsonl" | "csv" | "api";
    detections: Record<string, unknown>[];
    label_mapping?: Record<string, string>;
    replace_existing?: boolean;
  },
) {
  const { data } = await api.post<BenchmarkRun>(`/api/v1/benchmark-runs/${benchmarkRunId}/detector-output`, payload);
  return data;
}

export async function uploadBenchmarkDetectorOutput(benchmarkRunId: string, file: File, detectorName = "uploaded-detector", replaceExisting = false) {
  const body = new FormData();
  body.append("file", file);
  const { data } = await api.post<BenchmarkRun>(`/api/v1/benchmark-runs/${benchmarkRunId}/detector-output/upload`, body, {
    params: { detector_name: detectorName, replace_existing: replaceExisting },
  });
  return data;
}
