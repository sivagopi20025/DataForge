import axios from "axios";
import type { AnalyticsOverview, CatalogResponse, Domain, FilePreview, GeneratePayload, GenerateResponse, JobStatus, PaginatedRuns, RunDetail } from "@/types/api";

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010",
  timeout: 120000,
});

const browserApiKey = process.env.NEXT_PUBLIC_DATAFORGE_API_KEY;
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
