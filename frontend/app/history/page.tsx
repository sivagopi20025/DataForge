"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { ChevronDown, Clock3, Database, Download, Eye, FileArchive, Table2 } from "lucide-react";
import { getDownloadUrl, getFilePreview, getRun, getRunDownloadUrl, getRuns } from "@/lib/api";
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
  const [previewSelection, setPreviewSelection] = useState<PreviewSelection>(null);
  const [expandedRunIds, setExpandedRunIds] = useState<Set<string>>(() => new Set());
  const runsQuery = useQuery({ queryKey: ["runs", 25, 0], queryFn: () => getRuns(25, 0) });
  const runs = useMemo(() => runsQuery.data?.items ?? [], [runsQuery.data?.items]);
  const runDetailQueries = useQueries({
    queries: runs.map((run) => ({
      queryKey: ["run", run.id],
      queryFn: () => getRun(run.id),
      enabled: runsQuery.isSuccess,
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

  return (
    <div className="space-y-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-primary">History</p>
          <h1 className="mt-2 text-4xl font-bold tracking-tight">Run History</h1>
          <p className="mt-2 text-muted-foreground">Review each domain run, preview every generated table, or download all files as a ZIP.</p>
        </div>
        <Link href="/generator">
          <Button>Generate New Dataset</Button>
        </Link>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        <Metric label="Total Runs" value={formatNumber(runsQuery.data?.total ?? 0)} />
        <Metric label="Displayed" value={formatNumber(runs.length)} />
        <Metric label="Latest Status" value={latestStatus} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Runs</CardTitle>
          <CardDescription>Click a domain row to expand generated tables, preview data, and download individual files.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {runs.length ? (
            runs.map((run, index) => (
              <RunHistoryCard
                key={run.id}
                run={run}
                detail={runDetailQueries[index]?.data}
                detailLoading={runDetailQueries[index]?.isLoading ?? false}
                expanded={expandedRunIds.has(run.id)}
                previewSelection={previewSelection}
                preview={previewSelection?.runId === run.id ? previewQuery.data : undefined}
                previewLoading={previewSelection?.runId === run.id && previewQuery.isLoading}
                previewError={previewSelection?.runId === run.id ? previewQuery.error?.message : undefined}
                onToggle={() => toggleRun(run.id)}
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
  expanded,
  previewSelection,
  preview,
  previewLoading,
  previewError,
  onToggle,
  onPreview,
}: {
  run: RunSummary;
  detail?: RunDetail;
  detailLoading: boolean;
  expanded: boolean;
  previewSelection: PreviewSelection;
  preview?: FilePreview;
  previewLoading: boolean;
  previewError?: string;
  onToggle: () => void;
  onPreview: (fileId: string) => void;
}) {
  const generatedFiles = detail?.generated_files ?? [];

  return (
    <div className={cn("rounded-2xl border border-border bg-muted/30 p-4 transition", expanded && "bg-primary/5")}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <button type="button" onClick={onToggle} className="flex min-w-0 flex-1 items-center gap-3 rounded-2xl text-left transition hover:text-primary">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            <Database className="h-5 w-5" />
          </div>
          <div className="grid min-w-0 flex-1 gap-3 md:grid-cols-[minmax(0,1fr)_180px_220px] md:items-center">
            <div className="min-w-0">
              <p className="truncate font-semibold">{titleCase(run.domain)}</p>
            </div>
            <div className="text-sm font-semibold text-foreground">{formatNumber(run.record_count)} records</div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Clock3 className="h-4 w-4" />
              {formatDateTime(run.completed_at ?? run.started_at)}
            </div>
          </div>
          <ChevronDown className={cn("h-5 w-5 shrink-0 text-muted-foreground transition-transform", expanded && "rotate-180 text-primary")} />
        </button>

        <div className="flex items-center gap-2">
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
      <div className="mt-4 grid gap-4 xl:grid-cols-[380px_minmax(0,1fr)]">
        <div className="rounded-2xl border border-border bg-card p-3">
          <div className="mb-3 flex items-center justify-between gap-3 px-1">
            <div>
              <p className="text-sm font-bold">Generated Tables</p>
              <p className="text-xs text-muted-foreground">Preview or download each table file.</p>
            </div>
            {detailLoading ? <Badge>Loading</Badge> : <Badge>{generatedFiles.length} files</Badge>}
          </div>

          {detailLoading ? (
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

        <div className="min-w-0 rounded-2xl border border-border bg-card p-4">
          <div className="mb-3 flex items-center gap-2">
            <Table2 className="h-5 w-5 text-primary" />
            <div>
              <p className="font-bold">Preview</p>
              <p className="text-xs text-muted-foreground">Selected table data appears here.</p>
            </div>
          </div>
          <HistoryPreviewPanel isLoading={previewLoading} error={previewError} preview={preview} />
        </div>
      </div>
      ) : null}
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
