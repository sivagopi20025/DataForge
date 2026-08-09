"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Clock3, Database, Download, Eye, FileArchive, Table2, Trash2 } from "lucide-react";
import { deleteRun, deleteRuns, getDownloadUrl, getFilePreview, getRun, getRunDownloadUrl, getRuns } from "@/lib/api";
import type { FilePreview, RunDetail, RunSummary } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatNumber, titleCase } from "@/lib/utils";

type PreviewSelection = {
  runId: string;
  fileId: string;
} | null;

export default function RunHistoryPage() {
  const queryClient = useQueryClient();
  const [previewSelection, setPreviewSelection] = useState<PreviewSelection>(null);
  const [expandedRunIds, setExpandedRunIds] = useState<Set<string>>(() => new Set());
  const [selectedRunIds, setSelectedRunIds] = useState<Set<string>>(() => new Set());
  const runsQuery = useQuery({ queryKey: ["runs", 25, 0], queryFn: () => getRuns(25, 0) });
  const runs = useMemo(() => runsQuery.data?.items ?? [], [runsQuery.data?.items]);
  const selectedCount = selectedRunIds.size;
  const allVisibleSelected = runs.length > 0 && runs.every((run) => selectedRunIds.has(run.id));
  const deleteMutation = useMutation({
    mutationFn: (runIds: string[]) => (runIds.length === 1 ? deleteRun(runIds[0]) : deleteRuns(runIds)),
    onSuccess: (_, runIds) => {
      const removed = new Set(runIds);
      setSelectedRunIds((current) => new Set([...current].filter((id) => !removed.has(id))));
      setExpandedRunIds((current) => new Set([...current].filter((id) => !removed.has(id))));
      if (previewSelection && removed.has(previewSelection.runId)) {
        setPreviewSelection(null);
      }
      for (const runId of runIds) {
        queryClient.removeQueries({ queryKey: ["run", runId] });
      }
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
  });
  const runDetailQueries = useQueries({
    queries: runs.map((run) => ({
      queryKey: ["run", run.id],
      queryFn: () => getRun(run.id),
      enabled: expandedRunIds.has(run.id),
      staleTime: 30_000,
    })),
  });
  const previewQuery = useQuery({
    queryKey: ["history-file-preview", previewSelection?.runId, previewSelection?.fileId],
    queryFn: () => getFilePreview(previewSelection?.runId as string, previewSelection?.fileId as string, 50),
    enabled: Boolean(previewSelection),
  });

  if (runsQuery.isLoading) {
    return <div className="space-y-6">{Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-28" />)}</div>;
  }

  if (runsQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Run history unavailable</CardTitle>
          <CardDescription>{runsQuery.error.message}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const latestStatus = runs[0]?.status ? titleCase(runs[0].status) : "No runs";

  function toggleRun(runId: string) {
    const isExpanded = expandedRunIds.has(runId);
    if (isExpanded && previewSelection?.runId === runId) {
      setPreviewSelection(null);
    }
    setExpandedRunIds((current) => {
      const next = new Set(current);
      if (next.has(runId)) {
        next.delete(runId);
      } else {
        next.add(runId);
      }
      return next;
    });
  }

  function toggleSelectRun(runId: string) {
    setSelectedRunIds((current) => {
      const next = new Set(current);
      if (next.has(runId)) {
        next.delete(runId);
      } else {
        next.add(runId);
      }
      return next;
    });
  }

  function toggleSelectAllVisible() {
    setSelectedRunIds((current) => {
      const next = new Set(current);
      if (allVisibleSelected) {
        for (const run of runs) next.delete(run.id);
      } else {
        for (const run of runs) next.add(run.id);
      }
      return next;
    });
  }

  function requestDelete(runIds: string[]) {
    if (!runIds.length || deleteMutation.isPending) return;
    const confirmed = window.confirm(`Delete ${runIds.length} run${runIds.length === 1 ? "" : "s"} and generated files? This cannot be undone.`);
    if (confirmed) {
      deleteMutation.mutate(runIds);
    }
  }

  return (
    <div className="min-w-0 space-y-8">
      <header className="flex min-w-0 flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-primary">History</p>
          <h1 className="mt-2 text-4xl font-bold tracking-tight">Run History</h1>
          <p className="mt-2 text-muted-foreground">Review each domain run, preview every generated table, or download all files as a ZIP.</p>
        </div>
        <Link href="/generator">
          <Button>Generate New Dataset</Button>
        </Link>
      </header>

      <div className="grid min-w-0 gap-4 md:grid-cols-3">
        <Metric label="Total Runs" value={formatNumber(runsQuery.data?.total ?? 0)} />
        <Metric label="Displayed" value={formatNumber(runs.length)} />
        <Metric label="Latest Status" value={latestStatus} />
      </div>

      <Card>
        <CardHeader>
            <div className="flex min-w-0 flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <CardTitle>Recent Runs</CardTitle>
              <CardDescription>Click a domain row to expand generated tables, preview data, download files, or select runs for deletion.</CardDescription>
            </div>
            {runs.length ? (
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <label className="inline-flex h-11 items-center gap-2 rounded-xl border border-border bg-card px-3 text-sm font-semibold">
                  <input type="checkbox" checked={allVisibleSelected} onChange={toggleSelectAllVisible} className="h-4 w-4 accent-primary" />
                  Select visible
                </label>
                <Button
                  variant="danger"
                  disabled={selectedCount === 0 || deleteMutation.isPending}
                  onClick={() => requestDelete([...selectedRunIds])}
                >
                  {deleteMutation.isPending ? "Deleting..." : `Delete Selected (${selectedCount})`}
                </Button>
              </div>
            ) : null}
          </div>
          {deleteMutation.isError ? <p className="text-sm text-danger">{deleteMutation.error.message}</p> : null}
        </CardHeader>
        <CardContent className="min-w-0 space-y-4">
          {runs.length ? (
            runs.map((run, index) => (
              <RunHistoryCard
                key={run.id}
                run={run}
                detail={runDetailQueries[index]?.data}
                detailLoading={runDetailQueries[index]?.isLoading ?? false}
                detailError={runDetailQueries[index]?.error?.message}
                expanded={expandedRunIds.has(run.id)}
                selected={selectedRunIds.has(run.id)}
                deleting={deleteMutation.isPending}
                previewSelection={previewSelection}
                preview={previewSelection?.runId === run.id ? previewQuery.data : undefined}
                previewLoading={previewSelection?.runId === run.id && previewQuery.isLoading}
                previewError={previewSelection?.runId === run.id ? previewQuery.error?.message : undefined}
                onToggle={() => toggleRun(run.id)}
                onSelect={() => toggleSelectRun(run.id)}
                onDelete={() => requestDelete([run.id])}
                onPreview={(fileId) => setPreviewSelection({ runId: run.id, fileId })}
              />
            ))
          ) : (
            <div className="rounded-2xl border border-dashed border-border p-8 text-center">
              <p className="font-semibold">No run history yet.</p>
              <p className="mt-2 text-sm text-muted-foreground">Generate a dataset to create your first run history entry.</p>
              <Link href="/generator" className="mt-4 inline-block">
                <Button>Go to Generator</Button>
              </Link>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function RunHistoryCard({
  run,
  detail,
  detailLoading,
  detailError,
  expanded,
  selected,
  deleting,
  previewSelection,
  preview,
  previewLoading,
  previewError,
  onToggle,
  onSelect,
  onDelete,
  onPreview,
}: {
  run: RunSummary;
  detail?: RunDetail;
  detailLoading: boolean;
  detailError?: string;
  expanded: boolean;
  selected: boolean;
  deleting: boolean;
  previewSelection: PreviewSelection;
  preview?: FilePreview;
  previewLoading: boolean;
  previewError?: string;
  onToggle: () => void;
  onSelect: () => void;
  onDelete: () => void;
  onPreview: (fileId: string) => void;
}) {
  const generatedFiles = detail?.generated_files ?? [];
  const validationResults = detail?.validation_results ?? [];
  const issueManifest = detail?.issue_manifest ?? [];
  const failedChecks = validationResults.filter((item) => item.status !== "PASS");
  const validationSummary = getValidationSummary(run, validationResults);
  const validationLabel = run.scenario_outcome === "PASS" && validationSummary.status === "Failed" ? "Failed as expected" : validationSummary.status;
  const scenarioValidators = detail?.scenario_reports?.["scenario_execution_report.json"]?.scenario_validator_results ?? [];

  return (
    <div className={cn("min-w-0 overflow-hidden rounded-2xl border border-border bg-muted/30 p-4 transition", expanded && "bg-primary/5")}>
      <div className="grid min-w-0 gap-3 lg:grid-cols-[44px_minmax(0,1fr)_auto] lg:items-center">
        <label className="flex h-11 items-center justify-center rounded-xl border border-border bg-card text-sm font-semibold">
          <input
            type="checkbox"
            checked={selected}
            onChange={onSelect}
            className="h-4 w-4 accent-primary"
            aria-label={`Select ${titleCase(run.domain)} run ${run.id}`}
          />
        </label>
        <button type="button" onClick={onToggle} className="grid min-w-0 gap-3 rounded-2xl text-left transition hover:text-primary sm:grid-cols-[44px_minmax(0,1fr)_minmax(120px,170px)_minmax(160px,220px)_24px] sm:items-center">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            <Database className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="truncate font-semibold">{titleCase(run.domain)}</p>
            <p className="truncate text-xs text-muted-foreground">{run.scenario_name ? `Scenario: ${run.scenario_name}` : `Run ID: ${run.id}`}</p>
          </div>
          <div className="grid min-w-0 gap-1 text-sm">
            <span className="truncate font-semibold text-foreground">{formatNumber(run.record_count)} records</span>
            <span className="truncate text-xs uppercase tracking-[0.14em] text-muted-foreground">{formatFormat(run.format)}</span>
          </div>
          <div className="flex min-w-0 items-center gap-2 text-sm text-muted-foreground">
            <Clock3 className="h-4 w-4 shrink-0" />
            <span className="truncate">{formatDateTime(run.completed_at ?? run.started_at)}</span>
          </div>
          <ChevronDown className={cn("h-5 w-5 shrink-0 text-muted-foreground transition-transform", expanded && "rotate-180 text-primary")} />
        </button>

        <div className="flex min-w-0 flex-wrap items-center gap-2 lg:flex-nowrap lg:justify-end">
          {validationSummary.qualityScore !== null && validationSummary.qualityScore < 100 ? (
            <Badge className="border-warning/30 bg-warning/10 text-warning">Generated · Validation Failed</Badge>
          ) : null}
          <Badge className={statusBadgeClass(run.status)}>Generation: {titleCase(run.status)}</Badge>
          <Badge className={validationStatusBadgeClass(validationSummary.status)}>Validation: {validationLabel}</Badge>
          {run.scenario_outcome ? <Badge className={scenarioOutcomeBadgeClass(run.scenario_outcome)}>Scenario: {titleCase(run.scenario_outcome)}</Badge> : null}
          {run.scenario_severity ? <Badge>Severity: {titleCase(run.scenario_severity)}</Badge> : null}
          <Badge>Quality Score {validationSummary.qualityScore ?? "—"}</Badge>
          <button
            type="button"
            onClick={onDelete}
            disabled={deleting}
            title="Delete this run"
            aria-label={`Delete ${titleCase(run.domain)} run`}
            className="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-danger/30 bg-danger/10 text-danger transition hover:bg-danger hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Trash2 className="h-5 w-5" />
          </button>
          <a
            href={getRunDownloadUrl(run.id)}
            download
            title="Download all generated files as ZIP"
            aria-label={`Download ${titleCase(run.domain)} run as ZIP`}
            className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground transition hover:opacity-90"
          >
            <Download className="h-5 w-5" />
          </a>
        </div>
      </div>

      {expanded ? (
      <div className="mt-4 grid min-w-0 gap-4 xl:grid-cols-[minmax(280px,380px)_minmax(0,1fr)]">
        {run.scenario_name ? (
          <div className="xl:col-span-2 rounded-2xl border border-primary/20 bg-primary/5 p-4 text-sm">
            <p className="font-semibold">Scenario: {run.scenario_name}</p>
            <p className="mt-1 text-muted-foreground">
              Outcome: {titleCase(run.scenario_outcome ?? "pending")} · Severity: {titleCase(run.scenario_severity ?? "medium")} · Variations: {(run.scenario_variations ?? []).join(", ") || "default"}
            </p>
            {scenarioValidators.length ? (
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                {scenarioValidators.slice(0, 6).map((validator) => (
                  <div key={validator.validation_id} className="rounded-xl border border-border bg-card p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="truncate font-semibold">{validator.validation_id}</p>
                      <Badge className={validator.status === "PASS" ? "border-success/30 bg-success/10 text-success" : "border-danger/30 bg-danger/10 text-danger"}>{validator.status}</Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">Expected {validator.expected_count} · Detected {validator.detected_count} · Reconciliation {validator.reconciliation_status}</p>
                    <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{validator.message}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
        {detailError ? (
          <div className="xl:col-span-2 rounded-2xl border border-danger/30 bg-danger/5 p-4 text-sm text-danger">
            Unable to load run details: {detailError}
          </div>
        ) : null}
        <div className="min-w-0 rounded-2xl border border-border bg-card p-3">
          <div className="mb-3 flex items-center justify-between gap-3 px-1">
            <div>
              <p className="text-sm font-bold">Generated Tables</p>
              <p className="text-xs text-muted-foreground">Preview or download each table file.</p>
            </div>
            {detailLoading ? <Badge>Loading</Badge> : <Badge>{generatedFiles.length} files</Badge>}
          </div>

          {detailError ? (
            <div className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">Run details could not be loaded.</div>
          ) : detailLoading ? (
            <div className="space-y-2">{Array.from({ length: 3 }).map((_, index) => <Skeleton key={index} className="h-14" />)}</div>
          ) : generatedFiles.length ? (
            <div className="space-y-2">
              {generatedFiles.map((file) => {
                const isPreviewed = previewSelection?.runId === run.id && previewSelection.fileId === file.id;
                return (
                  <div
                    key={file.id}
                    className={cn(
                      "group flex items-center justify-between gap-3 rounded-xl border p-3 transition hover:border-primary/50 hover:bg-primary/5",
                      isPreviewed ? "border-primary bg-primary/5 ring-4 ring-primary/10" : "border-border bg-muted/30",
                    )}
                  >
                    <button type="button" onClick={() => onPreview(file.id)} className="flex min-w-0 flex-1 items-center gap-3 text-left">
                      <FileArchive className="h-4 w-4 shrink-0 text-primary" />
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold">{tableNameFromFile(file.file_name)}</p>
                        <p className="truncate text-xs text-muted-foreground">
                          {file.file_name} · {file.file_size_mb.toFixed(3)} MB
                        </p>
                      </div>
                    </button>
                    <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                      <button
                        type="button"
                        onClick={() => onPreview(file.id)}
                        className="rounded-lg p-2 text-muted-foreground transition hover:bg-card hover:text-primary"
                        aria-label={`Preview ${file.file_name}`}
                        title="Preview"
                      >
                        <Eye className="h-4 w-4" />
                      </button>
                      <a
                        href={getDownloadUrl(run.id, file.id)}
                        download
                        className="rounded-lg p-2 text-muted-foreground transition hover:bg-card hover:text-primary"
                        aria-label={`Download ${file.file_name}`}
                        title="Download"
                      >
                        <Download className="h-4 w-4" />
                      </a>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">No generated files found for this run.</div>
          )}
        </div>

        <div className="min-w-0 overflow-hidden rounded-2xl border border-border bg-card p-4">
          {detailError ? null : detailLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-72" />
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <div className="mb-3 flex items-center gap-2">
                  <Table2 className="h-5 w-5 text-primary" />
                  <div>
                    <p className="font-bold">Preview</p>
                    <p className="text-xs text-muted-foreground">Selected table data appears here.</p>
                  </div>
                </div>
                <HistoryPreviewPanel isLoading={previewLoading} error={previewError} preview={preview} />
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <DetailList
                  title="Validation Checks"
                  empty="No validation checks found for this run."
                  items={validationResults.map(validationResultToDetailItem)}
                />
                <DetailList
                  title="Detected Issues Summary"
                  empty={failedChecks.length ? "No issue manifest rows were stored." : "No failed checks or injected issue samples found."}
                  items={
                    issueManifest.length
                      ? issueManifest.map((item) => ({
                          id: String(item.id),
                          label: titleCase(item.issue_type),
                          meta: formatIssueManifestMeta(item),
                          failed: item.issue_count > 0,
                        }))
                      : failedChecks.slice(0, 6).map((item) => ({
                          ...validationResultToDetailItem(item),
                          failed: true,
                        }))
                  }
                />
              </div>

              <div className="flex justify-end">
                <Link href={`/runs/${run.id}`}>
                  <Button variant="secondary">Open full run detail</Button>
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
      ) : null}
    </div>
  );
}

type DetailItem = {
  id: string;
  label: string;
  meta: string;
  failed?: boolean;
  table?: string;
  column?: string;
  status?: string;
  score?: number | null;
  details?: string;
};

function DetailList({ title, empty, items }: {
  title: string;
  empty: string;
  items: DetailItem[];
}) {
  return (
    <div className="rounded-2xl border border-border bg-muted/20 p-3">
      <p className="text-sm font-bold">{title}</p>
      {items.length ? (
        <div className="mt-3 space-y-2">
          {items.slice(0, 8).map((item) => (
            <div key={item.id} className="rounded-xl border border-border bg-card p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold">{item.label}</p>
                  {item.table || item.column ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {item.table ? `Table: ${item.table}` : "Table: unavailable"}
                      {item.column ? ` · Column: ${item.column}` : ""}
                    </p>
                  ) : null}
                </div>
                <Badge className={item.failed ? "border-danger/30 bg-danger/10 text-danger" : "border-success/30 bg-success/10 text-success"}>
                  {item.status ? titleCase(item.status) : item.failed ? "Detected" : "Pass"}
                </Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{item.meta}</p>
              {item.details ? <p className="mt-1 text-xs text-muted-foreground">{item.details}</p> : null}
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">{empty}</p>
      )}
    </div>
  );
}

function HistoryPreviewPanel({ isLoading, error, preview }: { isLoading: boolean; error?: string; preview?: FilePreview }) {
  if (isLoading) {
    return <Skeleton className="h-72" />;
  }

  if (error) {
    return <div className="rounded-2xl border border-danger/30 bg-danger/5 p-4 text-sm text-danger">{error}</div>;
  }

  if (!preview) {
    return (
      <div className="flex min-h-72 items-center justify-center rounded-2xl border border-dashed border-border bg-muted/20 p-8 text-center text-sm text-muted-foreground">
        Click a table preview icon to inspect its rows here.
      </div>
    );
  }

  if (!preview.rows.length) {
    return <div className="rounded-2xl border border-border bg-muted/20 p-4 text-sm text-muted-foreground">No rows available to preview.</div>;
  }

  return (
    <div className="min-w-0">
      <div className="mb-3">
        <p className="font-semibold">{tableNameFromFile(preview.file_name)}</p>
        <p className="text-xs text-muted-foreground">
          {preview.file_name} · Showing {preview.row_count} of up to {preview.max_rows} preview rows
        </p>
      </div>
      <div className="max-h-[420px] overflow-auto rounded-2xl border border-border">
        <table className="min-w-full border-collapse text-left text-xs">
          <thead className="sticky top-0 bg-muted text-muted-foreground">
            <tr>
              {preview.columns.map((column) => (
                <th key={column} className="whitespace-nowrap border-b border-border px-3 py-2 font-semibold">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.rows.map((row, index) => (
              <tr key={index} className="odd:bg-card even:bg-muted/20">
                {preview.columns.map((column) => (
                  <td key={column} className="max-w-72 truncate whitespace-nowrap border-b border-border px-3 py-2 text-foreground" title={formatPreviewValue(row[column])}>
                    {formatPreviewValue(row[column])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function getValidationSummary(run: RunSummary, validationResults: RunDetail["validation_results"]) {
  const qualityScore = validationResults.find((item) => item.quality_score !== null)?.quality_score ?? run.quality_score;
  if (qualityScore === null || qualityScore === undefined) {
    return { status: "Not Run", qualityScore: null };
  }
  const hasFailedCheck = validationResults.some((item) => item.status !== "PASS");
  return { status: hasFailedCheck || qualityScore < 100 ? "Failed" : "Passed", qualityScore };
}

function validationResultToDetailItem(item: RunDetail["validation_results"][number]): DetailItem {
  const expected = parseJsonValue(item.expected_value);
  const actual = parseJsonValue(item.actual_value);
  const expectedObject = isPlainObject(expected) ? expected : {};
  const actualObject = isPlainObject(actual) ? actual : {};
  const table = stringOrUndefined(expectedObject.table);
  const column = stringOrUndefined(expectedObject.column);
  const expectedDetail = expectedObject.expected ?? expected;
  const actualDetail = actualObject.actual ?? actual;
  const failures = actualObject.failures;
  const message = stringOrUndefined(expectedObject.message);
  const metaParts = [
    `Status: ${item.status}`,
    `Score: ${item.quality_score ?? "—"}`,
    failures !== undefined && failures !== null ? `Failures: ${formatValidationValue(failures)}` : null,
  ].filter(Boolean);
  const detailParts = [
    expectedDetail !== undefined ? `Expected: ${formatValidationValue(expectedDetail)}` : null,
    actualDetail !== undefined ? `Actual: ${formatValidationValue(actualDetail)}` : null,
    message ? `Details: ${message}` : null,
  ].filter(Boolean);
  return {
    id: String(item.id),
    label: titleCase(item.validation_name),
    meta: metaParts.join(" · "),
    failed: item.status !== "PASS",
    table,
    column,
    status: item.status,
    score: item.quality_score,
    details: detailParts.join(" · "),
  };
}

function formatIssueManifestMeta(item: RunDetail["issue_manifest"][number]) {
  if (isSchemaDriftIssue(item.issue_type) && item.issue_percentage <= 0) {
    return item.issue_count > 0
      ? `${formatNumber(item.issue_count)} affected · table/schema-level issue`
      : "Detected · table/schema-level issue";
  }
  if (item.issue_percentage <= 0) {
    return item.issue_count > 0 ? `${formatNumber(item.issue_count)} affected` : "Detected";
  }
  return `${formatNumber(item.issue_count)} affected · ${item.issue_percentage}%`;
}

function isSchemaDriftIssue(issueType: string) {
  return issueType.toLowerCase().includes("schema_drift") || issueType.toLowerCase().includes("schema drift");
}

function parseJsonValue(value: string | null | undefined): unknown {
  if (value === null || value === undefined || value === "") return undefined;
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringOrUndefined(value: unknown) {
  return typeof value === "string" && value ? value : undefined;
}

function formatValidationValue(value: unknown): string {
  if (value === undefined || value === null || value === "") return "—";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
        <p className="mt-2 text-2xl font-bold">{value}</p>
      </CardContent>
    </Card>
  );
}

function tableNameFromFile(fileName: string) {
  return titleCase(fileName.replace(/\.[^.]+$/, ""));
}

function formatFormat(value: string) {
  return value === "database" ? "Database DDL" : value.toUpperCase();
}

function statusBadgeClass(status: string) {
  if (status === "completed") return "border-success/30 bg-success/10 text-success";
  if (status === "failed") return "border-danger/30 bg-danger/10 text-danger";
  return "border-warning/30 bg-warning/10 text-warning";
}

function validationStatusBadgeClass(status: string) {
  if (status === "Passed") return "border-success/30 bg-success/10 text-success";
  if (status === "Failed") return "border-danger/30 bg-danger/10 text-danger";
  return "border-warning/30 bg-warning/10 text-warning";
}

function scenarioOutcomeBadgeClass(status: string) {
  if (status === "PASS") return "border-success/30 bg-success/10 text-success";
  if (status === "PARTIAL") return "border-warning/30 bg-warning/10 text-warning";
  if (status === "FAIL") return "border-danger/30 bg-danger/10 text-danger";
  return "";
}

function formatPreviewValue(value: unknown) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}
