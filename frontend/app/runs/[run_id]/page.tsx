"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download, Eye, FileArchive, Table2 } from "lucide-react";
import { getDownloadUrl, getFilePreview, getRun } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber, titleCase } from "@/lib/utils";

export default function RunDetailPage() {
  const params = useParams<{ run_id: string }>();
  const [previewFileId, setPreviewFileId] = useState<string | null>(null);
  const runQuery = useQuery({ queryKey: ["run", params.run_id], queryFn: () => getRun(params.run_id) });
  const previewQuery = useQuery({
    queryKey: ["file-preview", params.run_id, previewFileId],
    queryFn: () => getFilePreview(params.run_id, previewFileId as string, 50),
    enabled: Boolean(previewFileId),
  });

  if (runQuery.isLoading) {
    return <div className="space-y-6">{Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-32" />)}</div>;
  }

  if (runQuery.isError || !runQuery.data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Run unavailable</CardTitle>
          <CardDescription>{runQuery.error?.message ?? "The run could not be loaded."}</CardDescription>
        </CardHeader>
        <CardContent>
          <Link href="/generator"><Button>Back to Generator</Button></Link>
        </CardContent>
      </Card>
    );
  }

  const run = runQuery.data;
  const qualityScore = run.validation_results.find((item) => item.quality_score !== null)?.quality_score ?? 100;
  const generatedAt = formatDateTime(run.completed_at ?? run.started_at);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between gap-4">
        <div>
          <Link href="/generator" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" /> Back to generator
          </Link>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">Run Results</h1>
          <p className="mt-2 text-muted-foreground">Run ID: {run.id}</p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/history">
            <Button variant="secondary">View history</Button>
          </Link>
          <Badge>{run.status}</Badge>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3 2xl:grid-cols-6">
        <Metric label="Domain" value={titleCase(run.domain)} />
        <Metric label="Load Type" value={titleCase(run.load_type)} />
        <Metric label="Format" value={run.format.toUpperCase()} />
        <Metric label="Records" value={formatNumber(run.record_count)} />
        <Metric label="Generated At" value={generatedAt} />
        <Metric label="Quality Score" value={`${Math.round(qualityScore)}`} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[390px_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Generated Files</CardTitle>
            <CardDescription>Hover a file to preview or download.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {run.generated_files.map((file) => {
              const isPreviewed = file.id === previewFileId;
              return (
                <div
                  key={file.id}
                  className={[
                    "group flex items-center justify-between gap-3 rounded-2xl border bg-muted/30 p-3 transition hover:border-primary/50 hover:bg-primary/5",
                    isPreviewed ? "border-primary ring-4 ring-primary/10" : "border-border",
                  ].join(" ")}
                >
                  <button type="button" onClick={() => setPreviewFileId(file.id)} className="flex min-w-0 flex-1 items-center gap-3 text-left">
                    <FileArchive className="h-5 w-5 shrink-0 text-primary" />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold">{file.file_name}</p>
                      <p className="text-xs text-muted-foreground">{file.file_format.toUpperCase()} · {file.file_size_mb.toFixed(3)} MB</p>
                    </div>
                  </button>
                  <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                    <button
                      type="button"
                      onClick={() => setPreviewFileId(file.id)}
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
          </CardContent>
        </Card>

        <Card className="min-w-0">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Table2 className="h-5 w-5 text-primary" />
              Data Preview
            </CardTitle>
            <CardDescription>
              {previewFileId ? "Showing the first rows for the selected file." : "Choose Preview on a generated file to inspect table data."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <FilePreviewPanel isLoading={previewQuery.isLoading} error={previewQuery.error?.message} preview={previewQuery.data} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function FilePreviewPanel({
  isLoading,
  error,
  preview,
}: {
  isLoading: boolean;
  error?: string;
  preview?: { file_name: string; columns: string[]; rows: Record<string, unknown>[]; row_count: number; max_rows: number };
}) {
  if (isLoading) {
    return <Skeleton className="h-80" />;
  }

  if (error) {
    return <div className="rounded-2xl border border-danger/30 bg-danger/5 p-4 text-sm text-danger">{error}</div>;
  }

  if (!preview) {
    return (
      <div className="flex min-h-80 items-center justify-center rounded-2xl border border-dashed border-border bg-muted/20 p-8 text-center text-sm text-muted-foreground">
        Hover a file for quick actions, then click the eye icon to preview rows here.
      </div>
    );
  }

  if (!preview.rows.length) {
    return <div className="rounded-2xl border border-border bg-muted/20 p-4 text-sm text-muted-foreground">No rows available to preview.</div>;
  }

  return (
    <div className="min-w-0">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="font-semibold">{preview.file_name}</p>
          <p className="text-xs text-muted-foreground">Showing {preview.row_count} of up to {preview.max_rows} preview rows</p>
        </div>
      </div>
      <div className="max-h-[560px] overflow-auto rounded-2xl border border-border">
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

function formatPreviewValue(value: unknown) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
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

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}
